from core import auth, utils
from core.cms import cms, queue, fileinfo
from core.ui import sidebar
from core.log import logger
from core.menu import generate_menu, icons
from core.search import (blog_search_results,
    blog_pages_in_category_search_results)

from core.models import (Struct, Site,
    template_tags, Page, Blog, Queue, Template, Theme,
    PageCategory, TemplateMapping, Media, Tag, template_type, publishing_mode,
    TemplateRevision, FileInfo)

from core.models.transaction import transaction
from core.libs.bottle import template, request, response
from settings import BASE_URL, RETRY_INTERVAL, APPLICATION_PATH
from . import listing, status_badge, save_action, search_contexts, report

import time

new_page_submission_fields = ('title', 'text', 'tag_text', 'excerpt')


@transaction
def blog(blog_id, errormsg=None):

    user = auth.is_logged_in(request)
    blog = Blog.load(blog_id)
    permission = auth.is_blog_member(user, blog)

    return listing(request, blog, blog.pages,
                   'blog', 'blog_menu',
                   user=user,
                   errormsg=errormsg,
                   search_ui='blog',
                   search_context=blog_search_results,
                   tags_data={'blog':blog}
                   )


@transaction
def blog_create(site_id):

    user = auth.is_logged_in(request)
    site = Site.load(site_id)
    permission = auth.is_site_admin(user, site)

    new_blog = Blog(
        name="",
        description="",
        url="",
        path="")

    tags = template_tags(site_id=site.id,
        user=user)

    tags.blog = new_blog
    from core.libs import pytz

    themes = Theme.select()

    return template('ui/ui_blog_settings',
        section_title="Create new blog",
        # search_context=(search_context['sites'], None),
        menu=generate_menu('site_create_blog', site),
        nav_default='all',
        timezones=pytz.all_timezones,
        themes=themes,
        ** tags.__dict__
        )


@transaction
def blog_create_save(site_id):

    user = auth.is_logged_in(request)
    site = Site.load(site_id)
    permission = auth.is_site_admin(user, site)

    errors = []

    new_blog = Blog(
            site=site,
            name=request.forms.getunicode('blog_name'),
            description=request.forms.getunicode('blog_description'),
            url=request.forms.getunicode('blog_url'),
            path=request.forms.getunicode('blog_path'),
            set_timezone=request.forms.getunicode('blog_timezone'),
            # theme=get_default_theme(),
            theme=Theme.default_theme()
            )

    try:
        new_blog.validate()
    except Exception as e:
        errors.extend(e.args[0])

    if len(errors) == 0:
        from core.libs.peewee import IntegrityError
        try:
            new_blog.setup(user, Theme.default_theme())
                # new_blog.theme)
        except IntegrityError as e:
            from core.utils import field_error
            errors.append(field_error(e))

    if len(errors) > 0:

        status = utils.Status(
            type='danger',
            no_sure=True,
            message='The blog could not be created due to the following problems:',
            message_list=errors)
        from core.libs import pytz
        tags = template_tags(site=site,
            user=user)
        tags.status = status
        tags.blog = new_blog
        themes = Theme.select()

        return template('ui/ui_blog_settings',
            section_title="Create new blog",
            # search_context=(search_context['sites'], None),
            menu=generate_menu('site_create_blog', site),
            nav_default='all',
            themes=themes,
            timezones=pytz.all_timezones,
            ** tags.__dict__
            )

    else:
        tags = template_tags(user=user, site=site,
            blog=new_blog)

        status = utils.Status(
            type='success',
            message='''
Blog <b>{}</b> was successfully created. You can <a href="{}/blog/{}/newpage">start posting</a> immediately.
'''.format(
                new_blog.for_display,
                BASE_URL, new_blog.id)
            )
        tags.status = status

        return report(tags, 'site_create_blog', site)


# TODO: make this universal to create a user for both a blog and a site
# use ka
@transaction
def blog_create_user(blog_id):
    '''
    Creates a user and gives it certain permissions within the context of a given blog
    '''

    user = auth.is_logged_in(request)
    blog = Blog.load(blog_id)
    permission = auth.is_blog_admin(user, blog)
    tags = template_tags(blog_id=blog.id,
        user=user)

    edit_user = Struct()
    edit_user.name = ""
    edit_user.email = ""

    return template('edit/user_settings',
        section_title="Create new blog user",
        # search_context=(search_context['sites'], None),
        edit_user=edit_user,
        **tags.__dict__
        )


@transaction
def blog_list_users(blog_id):

    user = auth.is_logged_in(request)
    blog = Blog.load(blog_id)
    permission = auth.is_blog_admin(user, blog)

    return listing(request, blog, blog.users,
                   'blog_users', 'blog_list_users',
                   user=user,
                   tags_data={'blog':blog}
                   )


@transaction
def blog_new_page(blog_id):
    '''
    Displays UI for newly created (unsaved) page
    '''
    user = auth.is_logged_in(request)
    blog = Blog.load(blog_id)
    permission = auth.is_blog_member(user, blog)

    tags = template_tags(
        blog=blog,
        user=user)

    tags.page = Page()

    referer = request.headers.get('Referer')
    if referer is None:
        referer = BASE_URL + "/blog/" + str(blog.id)

    blog_new_page = tags.page

    for n in new_page_submission_fields:
        blog_new_page.__setattr__(n, "")
        if n in request.query:
            blog_new_page.__setattr__(n, request.query.getunicode(n))

    import datetime

    blog_new_page.blog = blog
    blog_new_page.user = user
    blog_new_page.publication_date = datetime.datetime.utcnow()
    blog_new_page.basename = ''

    from core.cms import save_action_list

    from core.ui import kv
    kv_ui_data = kv.ui(blog_new_page.kv_list())

    try:
        html_editor_settings = Template.get(
        Template.blog == blog,
        Template.title == 'HTML Editor Init',
        Template.template_type == template_type.system
        ).body
    except Template.DoesNotExist:
        from core.static import html_editor_settings

    return template('edit/page',
        menu=generate_menu('create_page', blog),
        parent_path=referer,
        # search_context=(search_context['blog'], blog),
        html_editor_settings=html_editor_settings,
        sidebar=sidebar.render_sidebar(
            panel_set='edit_page',
            status_badge=status_badge,
            save_action=save_action,
            save_action_list=save_action_list,
            kv_ui=kv_ui_data,
            kv_object='Page',
            kv_objectid=None,
            **tags.__dict__),
        **tags.__dict__)


@transaction
def blog_new_page_save(blog_id):
    '''
    UI for saving a newly created page.
    '''
    user = auth.is_logged_in(request)
    blog = Blog.load(blog_id)
    permission = auth.is_blog_member(user, blog)

    tags = cms.save_page(None, user, blog)

    # TODO: move to model instance?
    logger.info("Page {} created by user {}.".format(
        tags.page.for_log,
        user.for_log))

    response.add_header('X-Redirect', BASE_URL + '/page/{}/edit'.format(str(tags.page.id)))

    return response


@transaction
def blog_previews_list(blog_id):

    user = auth.is_logged_in(request)
    blog = Blog.load(blog_id)
    permission = auth.is_blog_admin(user, blog)

    previews = blog.fileinfos.where(FileInfo.preview_path.is_null(False))

    return listing(request, blog, previews,
               'blog_previews', 'blog_previews',
               user=user,
               msg_float=False,
               tags_data={'blog':blog}
               )


@transaction
def blog_delete_preview(blog_id, preview_id):

    user = auth.is_logged_in(request)
    blog = Blog.load(blog_id)
    permission = auth.is_blog_admin(user, blog)

    f = lambda:None
    f.blog = blog

    if preview_id == 'all':
        previews_to_delete = blog.fileinfos.where(FileInfo.preview_path.is_null(False))
        message = 'All previews for blog {} deleted.'.format(blog.for_display)
        f.msg = 'Delete all'
    else:
        previews_to_delete = blog.fileinfos.where(FileInfo.id == preview_id)
        message = 'Preview for fileinfo {} deleted.'.format(preview_id)
        f.msg = 'Delete preview {}'.format(preview_id)

    for n in previews_to_delete:
        if n.page is not None:
            n.page.delete_preview()
        else:
            n.template_mapping.template.delete_preview()

    tags = template_tags(blog_id=blog.id, user=user)

    from core.utils import Status

    tags.status = Status(
        type='success',
        message=message,
        close=False,
        )

    return report(tags, 'blog_delete_preview', f)

#     return template('listing/report',
#         menu=generate_menu('blog_delete_preview', f),
#         icons=icons,
#         msg_float=False,
#          search_context=(search_context['blog'], blog),
#         **tags.__dict__)


@transaction
def blog_categories(blog_id):

    user = auth.is_logged_in(request)
    blog = Blog.load(blog_id)
    permission = auth.is_blog_editor(user, blog)
    errormsg = auth.check_category_editing_lock(blog, True)

    action = (
        ('Create new category',
        '{}/blog/{}/newcategory'.format(BASE_URL, blog.id)),
        )

    return listing(request, blog, blog.categories.select(),
                   'categories', 'blog_manage_categories',
                   user=user,
                   errormsg=errormsg,
                   tags_data={'blog':blog}
                   )


@transaction
def blog_pages_in_category(blog_id, category_id):

    user = auth.is_logged_in(request)
    blog = Blog.load(blog_id)
    permission = auth.is_blog_editor(user, blog)
    errormsg = auth.check_category_editing_lock(blog, True)

    from core.models import Category
    category = Category.load(category_id, blog_id=blog.id)

    return listing(request, category, category.pages,
                   'blog', 'blog_pages_in_category',
                   user=user,
                   errormsg=errormsg,
                   search_ui='blog_pages_in_category',
                   search_context=blog_pages_in_category_search_results,
                   tags_data={'blog':blog}
                   )


@transaction
def blog_templates(blog_id):
    '''
    List all templates in a given blog
    '''
    user = auth.is_logged_in(request)
    blog = Blog.load(blog_id)
    permission = auth.is_blog_designer(user, blog)

    reason = auth.check_template_lock(blog, True)

    tags = template_tags(blog_id=blog.id,
        user=user)

    tags.status = reason

    from core.libs.peewee import JOIN_LEFT_OUTER

    template_list = Template.select(Template, TemplateMapping).join(
        TemplateMapping, JOIN_LEFT_OUTER).where(
        (Template.blog == blog)
        ).order_by(Template.title)

    index_templates = template_list.select(Template, TemplateMapping).where(
        Template.template_type == template_type.index)

    page_templates = template_list.select(Template, TemplateMapping).where(
        Template.template_type == template_type.page)

    archive_templates = template_list.select(Template, TemplateMapping).where(
        Template.template_type == template_type.archive)

    template_includes = template_list.select(Template, TemplateMapping).where(
        Template.template_type == template_type.include)

    media_templates = template_list.select(Template, TemplateMapping).where(
        Template.template_type == template_type.media)

    code_templates = template_list.select(Template, TemplateMapping).where(
        Template.template_type == template_type.code)

    system_templates = template_list.select(Template, TemplateMapping).where(
        Template.template_type == template_type.system)

    from core.models import archive_defaults

    tags.list_items = (
        {'title':'Index Templates',
        'type': template_type.index,
        'data':index_templates,
        'defaults': archive_defaults[template_type.index]},
        {'title':'Page Templates',
        'type': template_type.page,
        'data':page_templates,
        'defaults':archive_defaults[template_type.page]},
        {'title':'Archive Templates',
        'type': template_type.archive,
        'data':archive_templates,
        'defaults': archive_defaults[template_type.archive]},
        {'title':'Includes',
        'type': template_type.include,
        'data':template_includes},
        {'title':'Media Templates',
        'type': template_type.media,
        'data':media_templates},
        {'title':'Code',
        'type': template_type.code,
        'data':code_templates},
        {'title':'System Templates',
        'type': template_type.system,
        'data':system_templates},
        )

    return template('ui/ui_blog_templates',
        icons=icons,
        section_title="Templates",
        publishing_mode=publishing_mode,
        search_context=(search_contexts['blog_templates'], blog),
        menu=generate_menu('blog_manage_templates', blog),
        templates_with_defaults=('Index', 'Page', 'Archive'),
        ** tags.__dict__)


@transaction
def blog_select_themes(blog_id):
    user = auth.is_logged_in(request)
    blog = Blog.load(blog_id)
    permission = auth.is_blog_designer(user, blog)
    errormsg = auth.check_template_lock(blog, True)

    class ThemeListing(Theme):

        @property
        def blog(self):
            return blog

        class Meta:
            db_table = 'theme'

    return listing(request, blog, ThemeListing.select().order_by(ThemeListing.title),
                   'themes', 'blog_manage_themes',
                   user=user,
                   errormsg=errormsg,
                   tags_data={'blog':blog}
                   )


@transaction
def blog_republish(blog_id, pass_id=1, item_id=0):
    user = auth.is_logged_in(request)
    blog = Blog.load(blog_id)
    permission = auth.is_blog_publisher(user, blog)

    data = []

    # check for dirty templates?

    from core import cms
    from core.libs.bottle import HTTPResponse
    from settings import BASE_PATH
    r = HTTPResponse()

    if pass_id == 1:
        cms.queue.queue_ssi_actions(blog)
        item_id = 0

        data.append("<h3>Queuing <b>{}</b> for republishing, pass {}, item {}</h3><hr>".format(
            blog.for_log,
            pass_id,
            item_id))

    elif pass_id == 2:
        cms.queue.queue_index_actions(blog, include_manual=True)
        item_id = 0

        data.append("<h3>Queuing <b>{}</b> for republishing, pass {}, item {}</h3><hr>".format(
            blog.for_log,
            pass_id,
            item_id))

    elif pass_id == 3:
        total = blog.pages.published.naive().count()
        pages = blog.pages.published.paginate(item_id, 20).naive()

        data.append("<h3>Queuing <b>{}</b> for republishing, pass {}, item {} of {}</h3><hr>".format(
            blog.for_log,
            pass_id,
            item_id * 20,
            total))

        if pages.count() > 0:
            cms.queue.queue_page_actions(pages, no_neighbors=True)
            item_id += 1
        else:
            item_id = 0

    if item_id == 0:
        pass_id += 1

    r.body = ''.join(data)

    if pass_id < 4:
        r.add_header('Refresh', "0;{}/blog/{}/republish/{}/{}".format(
        BASE_PATH,
        blog_id,
        pass_id,
        item_id))
    else:
        r.body = "Queue insertion finished."
        r.add_header('Refresh', "0;{}/blog/{}/publish".format(
        BASE_PATH,
        blog_id))

    return r


@transaction
def blog_republish_batch(blog_id):
    user = auth.is_logged_in(request)
    blog = Blog.load(blog_id)
    permission = auth.is_blog_publisher(user, blog)

    pages_to_queue = request.forms.getall('check')
    pages_that_can_be_queued = blog.pages.published.select().where(
        Page.id << pages_to_queue)
    page_count = pages_that_can_be_queued.count()
    response.add_header('X-Page-Count', page_count)
    if page_count > 0:
        queue.queue_page_actions(pages_that_can_be_queued)
        msg = '<b>OK:</b> {} pages queued for publication.'.format(page_count)
    else:
        msg = '<b>NOTE:</b> No pages queued for publication.'

    return msg


@transaction
def blog_purge(blog_id):
    '''
    UI for purging/republishing an entire blog
    Eventually to be reworked
    '''

    user = auth.is_logged_in(request)

    blog = Blog.load(blog_id)

    permission = auth.is_blog_publisher(user, blog)

    tags = template_tags(blog=blog, user=user)

    tags.report = cms.purge_blog(blog)

    return report(tags, 'blog_purge', blog)

#     return template('listing/report',
#         report=report,
#          search_context=(search_context['blog'], blog),
#         menu=generate_menu('blog_purge', blog),
#         msg_float=False,
#         **


@transaction
def blog_queue_clear(blog_id):
    '''
    Clear all pending jobs out of the queue
    '''
    user = auth.is_logged_in(request)
    blog = Blog.load(blog_id)
    permission = auth.is_blog_publisher(user, blog)

    Queue.clear(blog)


@transaction
def blog_queue(blog_id, status=None):

    user = auth.is_logged_in(request)
    blog = Blog.load(blog_id)
    permission = auth.is_blog_publisher(user, blog)

    tags = template_tags(blog_id=blog.id,
            user=user,
            status=status)

    return listing(request, blog, tags.queue,
                   'queue', 'blog_menu',
                   user=user,
                   tags_data={'blog':blog},
                   errormsg=tags.status
                   )


@transaction
def blog_queue_run(blog_id):

    user = auth.is_logged_in(request)
    blog = Blog.load(blog_id)
    permission = auth.is_blog_publisher(user, blog)

    import subprocess, sys
    taskpath = "{}/scripts/tasks.py".format(APPLICATION_PATH)
    pid = subprocess.Popen([sys.executable, taskpath, '--nowait']).pid
    msg = "<a href='../queue'>Queue</a> runner {} started with pid {}. ".format(taskpath, pid)

    from core.utils import Status
    status = Status(
            type='success',
            no_sure=True,
            message=msg)

    tags = template_tags(blog_id=blog.id,
            user=user,
            status=status
            )

    return report(tags, 'blog_menu', blog)


@transaction
def blog_break_queue(blog_id):
    user = auth.is_logged_in(request)
    blog = Blog.load(blog_id)
    permission = auth.is_blog_publisher(user, blog)

    Queue.stop(blog)

    tags = template_tags(blog=blog,
            user=user)

    return template('queue/queue_run_ui',
        start=None,
        action_url='',
        start_message='''
<p>Queue publishing stopped. Note that queued items are still in the queue,
and may still be processed on the next queue run.</p>
<p><a href="{}/blog/{}/queue/clear"><button class="btn">Clear the queue</button></a> to remove them entirely.</p>
'''.format(BASE_URL, blog_id),
        title='Publishing queue progress',
        # search_context=(search_context['blog_queue'], blog),
        menu=generate_menu('blog_queue', blog),
        **tags.__dict__)


@transaction
def blog_settings(blog_id, nav_setting):

    user = auth.is_logged_in(request)
    blog = Blog.load(blog_id)
    permission = auth.is_blog_admin(user, blog)

    auth.check_settings_lock(blog)

    tags = template_tags(blog_id=blog.id,
        user=user)

    tags.nav_default = nav_setting

    return blog_settings_output(tags)


@transaction
def blog_settings_save(blog_id, nav_setting):

    user = auth.is_logged_in(request)
    blog = Blog.load(blog_id)
    permission = auth.is_blog_admin(user, blog)

    _get = request.forms.getunicode

    # this could also be normalized?:
    # blog.form_gets([list here])
    # & you could always add custom fields after the fact

    blog.name = _get('blog_name', blog.name)
    blog.description = _get('blog_description', blog.description)
    blog.set_timezone = _get('blog_timezone')

    blog.url = _get('blog_url', blog.url)
    blog.path = _get('blog_path', blog.path)
    blog.base_extension = _get('blog_base_extension', blog.base_extension)
    blog.media_path = _get('blog_media_path', blog.media_path)

    from core.utils import Status
    from core.libs.peewee import IntegrityError
    errors = []

    try:
        blog.validate()
        blog.save()
    except IntegrityError as e:
        from core.utils import field_error
        errors.append(field_error(e))
    except Exception as e:
        errors.extend(e.args[0])

    # We could condense this all to:
    # blog.validate_and_save()
    # and just have it return errors as a list?

    if len(errors) > 0:

        status = Status(
            type='danger',
            no_sure=True,
            message='Blog settings could not be saved due to the following problems:',
            message_list=errors)
    else:
        status = Status(
            type='success',
            message="Settings for <b>{}</b> saved successfully.<hr/>It is recommended that you <a href='{}/blog/{}/purge'>republish this blog</a> immediately.".format(
                blog.for_display, BASE_URL, blog.id))

        logger.info("Settings for blog {} edited by user {}.".format(
            blog.for_log,
            user.for_log))

    tags = template_tags(user=user)

    tags.blog = blog
    tags.nav_default = nav_setting

    if status is not None:
        tags.status = status

    return blog_settings_output(tags)


def blog_settings_output(tags):
    from core.libs import pytz
    timezones = pytz.all_timezones
    path = '/blog/{}/settings/'.format(tags.blog.id)

    return template('ui/ui_blog_settings',
        # search_context=(search_context['blog'], tags.blog),
        timezones=timezones,
        menu=generate_menu('blog_settings', tags.blog),
        nav_tabs=(
            ('basic', path + 'basic', 'Basic'),
            ('dirs', path + 'dirs', 'Directories')
            ),
        **tags.__dict__)


@transaction
def blog_publish(blog_id):

    user = auth.is_logged_in(request)
    blog = Blog.load(blog_id)
    permission = auth.is_blog_publisher(user, blog)

    queue_length = Queue.job_counts(blog=blog)

    if queue_length > 0:
        start_message = template('queue/queue_run_include',
            queue=Queue.jobs(blog),
            percentage_complete=0,
            blog=blog,
            break_path='{}/blog/{}/publish/break'.format(BASE_URL, blog.id)
            )
        Queue.start(blog, queue_length)
    else:
        start_message = "Queue empty."

    tags = template_tags(blog_id=blog.id,
            user=user)

    #
    return template('queue/queue_run_ui',
        start=queue_length,
        start_message=start_message,
        action_url="../../blog/{}/publish/progress/{}".format(blog.id,
                                                              queue_length),
        title='Publishing queue progress',
        # search_context=(search_context['blog_queue'], blog),
        menu=generate_menu('blog_queue', blog),
        **tags.__dict__)


@transaction
def q_p(blog):
    return queue.process_queue(blog)


def blog_publish_progress(blog_id, original_queue_length):

    user = auth.is_logged_in(request)
    blog = Blog.load(blog_id)
    permission = auth.is_blog_publisher(user, blog)

    queue_count = 0

    control_jobs = Queue.control_jobs(blog)

    if control_jobs.count() > 0:
        # queue_count = queue.process_queue(blog)
        # queue_count = transaction(queue.process_queue)(blog)
        queue_count = q_p(blog)
        time.sleep(RETRY_INTERVAL * 5)
    else:
        queue_count = 0

    percentage_complete = int((1 - (int(queue_count) / int(original_queue_length))) * 100)
    import settings
    return template('queue/queue_run_include',
            queue_count=queue_count,
            blog=blog,
            break_path='{}/blog/{}/publish/break'.format(BASE_URL, blog.id),
            settings=settings,
            percentage_complete=percentage_complete)


def blog_publish_process(blog_id):

    user = auth.is_logged_in(request)
    blog = Blog.load(blog_id)
    permission = auth.is_blog_publisher(user, blog)

    control_jobs = Queue.control_jobs(blog)

    if control_jobs.count() > 0:
        queue_count = q_p(blog)
        # queue_count = transaction(queue.process_queue)(blog)
        time.sleep(RETRY_INTERVAL * 5)
    else:
        jobs = Queue.jobs(blog)
        if jobs.count() > 0:
            queue_count = jobs.count()
            Queue.start(blog, queue_count)
            queue_count = q_p(blog)
            # queue_count = transaction(queue.process_queue)(blog)
            time.sleep(RETRY_INTERVAL * 5)
        else:
            queue_count = 0

    import settings
    return template('queue/queue_counter_include',
            blog=blog,
            settings=settings,
            queue_count=queue_count)


@transaction
def blog_save_theme(blog_id):
    user = auth.is_logged_in(request)
    blog = Blog.load(blog_id)
    permission = auth.is_blog_publisher(user, blog)
    reason = auth.check_template_lock(blog)

    tags = template_tags(blog=blog,
            user=user)

    from core.utils import Status, create_basename_core

    if request.method == 'POST':

        theme = Theme(
            title=request.forms.getunicode('theme_title'),
            description=request.forms.getunicode('theme_description'),
            json='')

        export = blog.export_theme(theme.title, theme.description, user)

        from settings import THEME_FILE_PATH  # , _sep
        import os

        directory_name = create_basename_core(theme.title)
        dirs = [x[0] for x in os.walk(THEME_FILE_PATH)]
        dir_name_ext = 0
        dir_name_full = directory_name

        while 1:
            if dir_name_full in dirs:
                dir_name_ext += 1
                dir_name_full = directory_name + "-" + str(dir_name_ext)
                continue
            else:
                break

        dir_name_final = os.path.join(THEME_FILE_PATH, dir_name_full)
        os.makedirs(dir_name_final)
        theme.json = dir_name_full
        theme.save()

        Template.update(theme=theme).where(Template.blog == blog).execute()
        TemplateRevision.update(theme=theme).where(TemplateRevision.blog == blog).execute()

        blog.theme = theme
        blog.theme_modified = False
        blog.save()

        for n in export:
            with open(os.path.join(dir_name_final,
                n), "w", encoding='utf-8') as output_file:
                output_file.write(export[n])

        save_tpl = 'listing/report'
        status = Status(
            type='success',
            close=False,

            message='''
Theme <b>{}</b> was successfully saved from blog <b>{}</b>.
'''.format('', blog.for_display, ''),
            action='Return to theme list',
            url='{}/blog/{}/themes'.format(
                BASE_URL, blog.id)
            )
    else:

        save_tpl = 'edit/theme_save'
        status = None

    tags.status = status if reason is None else reason

    import datetime

    # TODO: eventually this will be migrated to the report function
    # but it's a little complex for that now due to the funtion logic

    return template(save_tpl,
        menu=generate_menu('blog_save_theme', blog),
        # search_context=(search_context['blog'], blog),
        theme_title=blog.theme.title + " (Revised {})".format(datetime.datetime.now()),
        theme_description=blog.theme.description,
        msg_float=False,
        ** tags.__dict__)


@transaction
def blog_apply_theme(blog_id, theme_id):
    user = auth.is_logged_in(request)
    blog = Blog.load(blog_id)
    permission = auth.is_blog_publisher(user, blog)
    reason = auth.check_template_lock(blog)

    theme = Theme.load(theme_id)

    tags = template_tags(blog=blog,
            user=user)

    from core.utils import Status

    if request.forms.getunicode('confirm') == user.logout_nonce:

        from core.models import db
        with db.atomic() as txn:
            blog.apply_theme(theme, user)

        status = Status(
            type='success',
            close=False,
            message='''
Theme <b>{}</b> was successfully applied to blog <b>{}</b>.</p>
It is recommended that you <a href="{}">republish this blog.</a>
'''.format(theme.for_display, blog.for_display, '{}/blog/{}/republish'.format(
                BASE_URL, blog.id))
            )

    else:

        status = Status(
            type='warning',
            close=False,
            message='''
You are about to apply theme <b>{}</b> to blog <b>{}</b>.</p>
<p>This will OVERWRITE AND REMOVE ALL EXISTING TEMPLATES on this blog!</p>
'''.format(theme.for_display, blog.for_display),
            url='{}/blog/{}/themes'.format(
                BASE_URL, blog.id),
            yes={'id':'delete',
                'name':'confirm',
                'label':'Yes, I want to apply this theme',
                'value':user.logout_nonce},
            no={'label':'No, don\'t apply this theme',
                'url':'{}/blog/{}/themes'.format(
                BASE_URL, blog.id)}
            )

    tags.status = status if reason is None else reason

    return report(tags, 'blog_apply_theme', [blog, theme])

#     return template('listing/report',
#         menu=generate_menu('', ),
#         # search_context=(search_context['blog'], blog),
#         msg_float=False,
#         **tags.__dict__)


# @transaction
def blog_import (blog_id):
    user = auth.is_logged_in(request)
    blog = Blog.load(blog_id)
    permission = auth.is_blog_publisher(user, blog)
    reason = auth.check_template_lock(blog, True)

    tags = template_tags(blog=blog,
        user=user)

    import os, settings
    import_path = os.path.join(
        settings.APPLICATION_PATH,
        "data",
        "import.json")

    tags.status = reason

    if request.method == "POST":
        from core.models import db
        tpl = ''
        with db.atomic() as txn:
            import json
            from core.utils import string_to_date

            import_path = request.forms.getunicode('import_path')
            with open(import_path, 'r', encoding='utf8') as f:
                json_data = json.load(f)

            from core.models import page_status, MediaAssociation, Category
            from core.error import PageNotChanged
            from core.libs.peewee import InterfaceError
            from core.cms import media_filetypes
            format_str = "<b>{}</b> / (<i>{}</i>)"

            # TODO: go in chunks of 50 or something?
            # allow graceful disconnection?
            for n in json_data:
                q = []
                n_id = n['id']
                q.append("Checking {}".format(n_id))
                changed = False
                found = False
                match = Page.kv_get('legacy_id', n_id)
                if match.count() > 0:
                    if match[0].object_ref.blog == blog:
                        found = True
                        q.append(match[0].key + "/" + match[0].value + " / Exists: " + format_str.format(n['title'], n_id))
                        existing_entry = Page.load(match[0].objectid)
                        update = existing_entry.kv_get('update').count()
                        # raise Exception(update)
                        q.append('{} / {}'.format(string_to_date(n['modified_date']).replace(tzinfo=None), existing_entry.modified_date
                            ))
                        if string_to_date(n['modified_date']).replace(tzinfo=None) <= existing_entry.modified_date and update == 0:
                            q.append('Existing page {} not changed.'.format(existing_entry.id))
                        else:
                            changed = True
                            q.append('Updating data for existing page {}.'.format(existing_entry.id))
                            existing_entry.title = n['title']
                            existing_entry.text = n['text']
                            existing_entry.basename = n['basename']
                            existing_entry.excerpt = n['excerpt']

                            existing_entry.created_date = string_to_date(n['created_date']).replace(tzinfo=None)
                            existing_entry.modified_date = string_to_date(n['modified_date']).replace(tzinfo=None)
                            existing_entry.publication_date = string_to_date(n['publication_date']).replace(tzinfo=None)

                            try:
                                existing_entry.save(user, False, False, 'New revision from import')
                            except PageNotChanged:
                                pass
                            except InterfaceError:
                                raise Exception("Error saving {}. Check the JSON to make sure it's valid.".format(n_id))

                            for media in existing_entry.media:
                                media.kv_del()

                            existing_entry.clear_categories()
                            existing_entry.clear_kvs()
                            existing_entry.clear_tags()
                            existing_entry.clear_media()

                            entry = existing_entry

                if found is False:
                    q.append("Creating: " + format_str.format(n['title'], n_id))
                    changed = True
                    new_entry = Page(
                        title=n['title'],
                        text=n['text'],
                        basename=n['basename'],
                        excerpt=n['excerpt'],
                        user=user,
                        blog=blog,
                        created_date=string_to_date(n['created_date']),
                        publication_date=string_to_date(n['publication_date']),
                        modified_date=string_to_date(n['modified_date']),
                    )

                    new_entry.modified_date = new_entry.publication_date

                    if n['status'] in ('Publish', 'Published', 'Live'):
                        new_entry.status = page_status.published

                    new_entry.save(user)

                    entry = new_entry

                    q.append("New ID: {}".format(entry.id))

                    # Everything from here on out is

                if changed:

                    # Register a legacy ID for the page

                    entry.kv_set("legacy_id", n["id"])
                    entry.kv_set("legacy_user", n["user_id"])

                    # Category assignments

                    categories = n['categories']
                    if categories == []:
                        saved_page_category = PageCategory.create(
                            page=entry,
                            category=blog.default_category,
                            primary=True).save()
                    else:
                        primary = True
                        for category in categories:
                            cat_exists = False

                            category_id = category['id']
                            existing_category = Category.kv_get('legacy_id', category_id)
                            if existing_category.count() > 0:
                                if existing_category[0].object_ref.blog == blog:
                                    cat_exists = True

                            if cat_exists is False:

                                q.append('Created new category {}/{}'.format(
                                    category_id, category['name']
                                    ))
                                new_category = Category.create(
                                    blog=blog,
                                    title=category['name'],
                                    parent_category=getattr(category, 'parent', None)
                                    )
                                new_category.save()

                                new_category.kv_set('legacy_id',
                                    category_id
                                    )
                            else:
                                new_category = Category.load(existing_category[0].objectid)
                                q.append('Added to existing category {}/{}'.format(
                                    new_category.id, category['name']
                                    ))

                            saved_page_category = PageCategory.create(
                                page=entry,
                                category=new_category,
                                primary=primary
                                ).save()
                            primary = False

                    # Check to make sure a default category exists for the whole blog.
                    # If not, assign one based on the lowest ID.
                    # This can always be reassigned later.

                    # Register tags

                    tags_added, tags_existing, _ = Tag.add_or_create(
                        n['tags'], page=entry)

                    q.append('Tags added: {}'.format(','.join(n.tag for n in tags_added)))
                    q.append('Tags existing: {}'.format(','.join(n.tag for n in tags_existing)))

                    # Register KVs

                    kvs = n['kvs']
                    for key in kvs:
                        if key != "":
                            value = kvs[key]
                            entry.kv_set(key, value)
                            q.append('KV: {}:{}'.format(key, value))

                    # Register media

                    media = n['media']

                    for m in media:

                        if 'path' not in m:
                            continue

                        path = os.path.split(m['path'])

                        try:
                            new_media = Media.get(Media.url == m['url'])
                        except:
                            new_media = Media(
                                filename=path[1],
                                path=m['path'],
                                url=m['url'],
                                type=media_filetypes.image,
                                created_date=string_to_date(m['created_date']),
                                modified_date=string_to_date(m['modified_date']),
                                friendly_name=m['friendly_name'],
                                user=user,
                                blog=blog,
                                site=blog.site
                                )

                        # TODO: RBF
                        try:
                            new_media.save()
                        except Exception:
                            continue

                        media_association = MediaAssociation(
                            media=new_media,
                            page=entry)

                        media_association.save()

                        # Save legacy ID to KV on media

                        if 'id' in m:
                            new_media.kv_set('legacy_id', m['id'])

                        q.append('IMG: {}'.format(new_media.url))

                        # add tags for media

                        q.append('Tags: {}'.format(m['tags']))
                        new_tags = Tag.add_or_create(m['tags'], media=new_media)

                        kvs = m['kvs']
                        for key in kvs:
                            value = kvs[key]
                            new_media.kv_set(key, value)
                            q.append('KV: {}:{}'.format(key, value))

                    fileinfo.build_pages_fileinfos((entry,))
                    fileinfo.build_archives_fileinfos((entry,))

                tpl += ('<p>'.join(q)) + '<hr/>'
        return tpl

        # TODO:

        # Import or create categories as needed
        # Categories in export will need to have parent-child data
        # categories should have legacy identifiers where possible too

        # Import image files, assign those legacy KV identifiers
        # Modify URLs for imported images in posts
        # Make importing of image assets optional

    else:
        tpl = template('ui/ui_blog_import',
            menu=generate_menu('blog_import', blog),
            # search_context=(search_context['blog'], blog),
            import_path=import_path,
            **tags.__dict__)

        return tpl

