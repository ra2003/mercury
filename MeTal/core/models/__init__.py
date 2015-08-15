import datetime, sys

import settings as _settings

from core import utils as _utils
from core.utils import tpl, date_format, html_escape, csrf_tag, csrf_hash, trunc

from settings import (DB_TYPE, DESKTOP_MODE, BASE_URL_ROOT, BASE_URL, DB_TYPE_NAME,
        SECRET_KEY, ENFORCED_CHARFIELD_CONSTRAINT)

from core.libs.bottle import request, url, _stderr
from core.libs.peewee import DeleteQuery, fn  # , BaseModel

from core.libs.playhouse.sqlite_ext import (Model, PrimaryKeyField, CharField,
   TextField, IntegerField, BooleanField, ForeignKeyField, DateTimeField, Check)

from functools import wraps

class EnforcedCharField(CharField):
    def __init__(self, max_length=255, *args, **kwargs):
        self.max_length = max_length
        super(CharField, self).__init__(*args, **kwargs)

    def db_value(self, value):
        if value is None:
            length = 0
        else:
            try:
                length = len(str.encode(value))
            except TypeError:
                length = len(value)

        if length > ENFORCED_CHARFIELD_CONSTRAINT:
            from core.error import DatabaseError
            raise DatabaseError("The field '{}' cannot be longer than {} bytes. ({})".format(
                self.name,
                ENFORCED_CHARFIELD_CONSTRAINT,
                request.url))
        return super(CharField, self).db_value(value)

class Struct(object):
    pass

db = DB_TYPE

parent_obj = {
    'Page':'Blog',
    'Blog':'Theme',
    'Theme':'Site',
    'Site':'System',
    'Log':'System',
    'PageRevision':'Page',
    'PageCategory':'Page',
    }

# lookup not required for this, so a struct
template_type = Struct()
template_type.index = "Index"
template_type.page = "Page"
template_type.archive = "Archive"
template_type.media = "Media"
template_type.include = "Include"

# lookup required, so a dict
publishing_mode = {
        'Immediate':{
            'label':'primary',
            'description':'Changes are pushed to the queue and processed immediately.'
            },
        'Batch only':{
            'label':'success',
            'description':'Changes are pushed to the queue but held for whenever the queue is next triggered.'},
        'Manual':{
            'label':'warning',
            'description':'Changes are published only when "regenerate pages" is selected.'},
        'Do not publish':{
            'label':'danger',
            'description':'Changes are never published.'},
        'Include':{
            'label':'default',
            'description':'Changes are only published when the include is present in another template.'
            }
    }

publishing_modes = (
    'Immediate',
    'Batch only',
    'Manual',
    'Do not publish',
    'Include'
    )

page_status_list = (
    ('unpublished', 'Unpublished', 1),
    ('published', 'Published', 2),
    ('scheduled', 'Scheduled', 3)
    )

page_status = Struct()
page_status.ids = Struct()
page_status.statuses = []
page_status.modes = {}
page_status.id = {}

for n in page_status_list:
    page_status.__setattr__(n[0], n[1])
    page_status.ids.__setattr__(n[0], n[2])
    page_status.statuses.append([n[2], n[1]])
    page_status.modes[n[2]] = n[1]
    page_status.id[n[1]] = n[2]


class BaseModel(Model):

    class Meta:
        database = db

    def parent(self):
        try:
            return parent_obj[self.__class__.__name__]
        except KeyError:
            return 'System'

    def add_kv(self, **kw):

        kv = KeyValue(
            object=kw['object'],
            objectid=kw['objectid'],
            key=kw['key'],
            value=kw['value'],
            parent=kw['parent'] if 'parent' in kw else None,
            is_schema=kw['is_schema'] if 'is_schema' in kw else False,
            is_unique=kw['is_unique'] if 'is_unique' in kw else False,
            value_type=kw['value_type'] if 'value_type' in kw else ''
            )

        kv.save()

        return kv

    def remove_kv(self, **kw):
        pass


    @property
    def n_t(self):
        # TODO: replace this with proxies for name in all fields that need it
        try:
            name = self.name
        except:
            name = self.title

        if name is None or name == "":
            return "[Untitled]"
        return trunc(name)

    @property
    def as_text(self):
        '''
        Returns a text-only, auto-escaped version of the object title.
        '''
        return html_escape(self.n_t)

    @property
    def for_log(self):
        '''
        Returns a version of the object title formatted for a log entry, which will be auto-escaped.
        '''
        return "'{}' (#{})".format(
            self.n_t, self.id)

    @property
    def for_listing(self):
        '''
        Returns a version of the object title as an HTML link, with an escaped title.
        '''
        try:
            listing_id = "id='list_item_" + str(self.id) + "'"
        except AttributeError:
            listing_id = self.listing_id
        return "<a {id} href='{link}'>{text}</a>".format(
            id=listing_id,
            link=self.link_format,
            text=html_escape(self.n_t))

    @property
    def for_display(self):
        '''
        Returns a version of the object title formatted for display in a header or other object,
        which will be auto-escaped.
        '''
        return "{} (#{})".format(
            self.for_listing,
            self.id)


    def kvs(self, key=None, context=None):

        # need context object
        # e.g., for a page tag that only shows up on certain blogs

        object_name = self.__class__.__name__
        original_object_name = object_name

        if context is not None:
            kv_context = KeyValue.select().where(
                KeyValue.parent << context)
        else:
            kv_context = KeyValue.select()

        while True:

            kv_all = kv_context.select().where(
                KeyValue.object == object_name)


            if kv_all.count() != 0:

                if key is not None:

                    kv_key = kv_all.select().where(
                        KeyValue.key == key)
                else:
                    kv_key = kv_all.select()

                if kv_key.count() != 0:

                    kv = kv_key.select().where(KeyValue.objectid == self.id)

                    if kv.count() != 0:
                        break

                    kv = kv_key.select().where(KeyValue.objectid == 0)

                    if kv.count() != 0:
                        break
            try:
                object_name = parent_obj[object_name]
            except KeyError:
                raise KeyError('Key {} not found in {} (searched through to {}).'.format(
                    key, original_object_name, object_name)
                    )

        return kv

    def kv(self, key=None, context=None):
        kv = self.kvs(key, context)
        if kv.count() > 0:
            return kv[0]
        else:
            return None

class Log(BaseModel):
    date = DateTimeField(default=datetime.datetime.now, index=True)
    level = IntegerField()
    message = TextField()

class User(BaseModel):

    name = EnforcedCharField(index=True, null=False, unique=True)
    email = EnforcedCharField(index=True, null=False, unique=True)
    password = CharField(null=False)
    avatar = IntegerField(null=True)  # refers to an asset ID
    last_login = DateTimeField(null=True)
    path_prefix = "/system"

    site = None
    blog = None

    logout_nonce = CharField(max_length=64, null=True, default=None)

    def from_site(self, site):
        self.site = site
        self.path_prefix = "/site/{}".format(str(site.id))
        return self

    def from_blog(self, blog):
        self.blog = blog
        self.path_prefix = "/blog/{}".format(str(blog.id))
        return self

    # for creating new post from main menu, among other things
    def blogs(self):

        from core.auth import role, bitmask, get_permissions

        permissions = get_permissions(self, level=bitmask.contribute_to_blog)

        if permissions[0].permission & role.SYS_ADMIN:
            all_blogs = Blog.select()
            return all_blogs

        '''
        permissions = Permission.select(
            Permission.blog).where(
            Permission.user == self,
            Permission.blog >0,
            Permission.permission.bin_and(bitmask))
        '''
        # for n in permissions:
            # print (n.permission, n.blog.id, n.site.id)

        blogs = Blog.select().where(
            Blog.id << permissions.select(Permission.blog).tuples())

        return blogs

    def sites(self, bitmask=1):
        sites = Permission.select().where(
            Permission.user == self,
            Permission.site > 0,
            Permission.permission.bin_and(bitmask))

        return sites

    @property
    def link_format(self):
        return "{}{}/user/{}".format(BASE_URL, self.path_prefix, self.id)


class SiteBase(BaseModel):

    name = TextField()
    url = CharField()
    path = EnforcedCharField(index=True, unique=True)
    local_path = EnforcedCharField(index=True, unique=True)
    base_index = CharField(null=False, default='index')
    base_extension = CharField(null=False, default='html')
    description = TextField()
    media_path = TextField(default='/media')
    editor_css = TextField(null=True)


class ConnectionBase(BaseModel):

    remote_connection = CharField(null=True, default='ftp')
    remote_address = CharField(null=True)
    remote_login = CharField(null=True)
    remote_password = CharField(null=True)

class Theme(BaseModel):
    title = TextField()
    description = TextField()
    json = TextField(null=True)

class Site(SiteBase, ConnectionBase):

    @property
    def link_format(self):
        return "{}/site/{}".format(
            BASE_URL, self.id)

    @property
    def blogs(self):
        return Blog.select().where(Blog.site == self)



    def pages(self, page_list=None):

        blogs = Blog.select(Blog.id).where(
            Blog.site == self).tuples()

        pages = Page.select(Page, PageCategory).where(
            Page.blog << blogs).join(
            PageCategory).where(
            PageCategory.primary == True).order_by(
            Page.publication_date.desc(), Page.id.desc())

        if page_list is not None:
            pages = pages.where(Page.id << page_list)

        return pages

    def module(self, module_name):
        pass


    @property
    def users(self):

        site_user_list = Permission.select(fn.Distinct(Permission.user)).where(
            Permission.site << [self.id, 0]).tuples()

        site_users = User.select().where(User.id << site_user_list)

        return site_users

    @property
    def templates(self):
        '''
        Returns all templates associated with a given blog.
        '''
        templates_in_site = Template.select().where(Template.site == self)

        return templates_in_site

    def template(self, template_id):

        templates_in_site = Template.select().where(Template.site == self, Template.id == template_id)

        return templates_in_site

    @property
    def permalink(self):
        '''
        Returns the permalink for a site.
        '''
        return self.url

    @property
    def index_file(self):
        '''
        Returns the index filename used in a given site.
        '''
        return self.base_index + "." + self.base_extension

    @property
    def media(self):
        '''
        Stub for: Returns iterable of all Media types associated with a site.
        '''
        pass

class Blog(SiteBase):
    site = ForeignKeyField(Site, null=False, index=True)
    theme = ForeignKeyField(Theme, null=False, index=True)


    @property
    def link_format(self):
        return "{}/blog/{}".format(
            BASE_URL, self.id)

    @property
    def media_path_(self, media_object=None):

        tags = template_tags(
            media=media_object,
            blog=self)

        template = tpl(self.media_path,
            **tags)

        # TODO: strip all newlines for a multi-line template?

        return template


    @property
    def users(self):

        blog_user_list = Permission.select(fn.Distinct(Permission.user)).where(
            Permission.site << [self.site, 0],
            Permission.blog << [self.id, 0]).tuples()

        blog_users = User.select().where(User.id << blog_user_list)

        return blog_users

    @property
    def max_revisions(self):
        return int(self.kv('MaxPageRevisions').value)

    @property
    def categories(self):
        '''
        Lists all categories for this blog in their proper hierarchical order.
        '''
        pass


    @property
    def permalink(self):
        return self.url

    def module(self, module_name):
        '''
        Returns a module from the current blog that matches this name.
        If no module of the name is found, it will attempt to also import a template.
        '''
        pass

    def pages(self, page_list=None):

        pages = Page.select(Page, PageCategory).where(
            Page.blog == self.id).join(
            PageCategory).where(
            PageCategory.primary == True).order_by(
            Page.publication_date.desc(), Page.id.desc())

        if page_list is not None:
            pages = pages.select().where(Page.id << page_list)

        return pages

    def published_pages(self):

        published_pages = self.pages().select().where(Page.status == page_status.published)

        return published_pages

    def last_n_pages(self, count=0):
        '''
        Returns the most recent pages posted in a blog, ordered by publication date.
        Set count to zero to retrieve all published pages.
        '''

        last_n_pages = self.published_pages().select().order_by(
            Page.publication_date.desc())

        if count > 0:
            last_n_pages = last_n_pages.select().limit(count)

        return last_n_pages

    def last_n_edited_pages(self, count=5):

        last_n_edited_pages = self.pages().select().order_by(Page.modified_date.desc()).limit(count)

        return last_n_edited_pages

    @property
    def index_file(self):
        return self.base_index + "." + self.base_extension

    @property
    def media(self):
        '''
        Returns all Media types associated with a given blog.
        '''
        media = Media.select().where(Media.blog == self)

        return media

    @property
    def templates(self):
        '''
        Returns all templates associated with a given blog.
        '''
        templates_in_blog = Template.select().where(Template.blog == self)

        return templates_in_blog

    def template(self, template_id):

        template_in_blog = Template.select().where(Template.blog == self, Template.id == template_id)

        return template_in_blog

    @property
    def index_templates(self):

        index_templates_in_blog = self.templates.select().where(Template.template_type ==
            template_type.index)

        return index_templates_in_blog

    @property
    def archive_templates(self):

        archive_templates_in_blog = self.templates.select().where(Template.template_type ==
            template_type.archive)

        return archive_templates_in_blog

    @property
    def template_mappings(self):
        '''
        Returns all template mappings associated with a given blog.
        '''

        template_mappings_in_blog = TemplateMapping.select().where(TemplateMapping.id <<
            self.templates.select(Template.id))

        return template_mappings_in_blog

    @property
    def fileinfos(self):
        '''
        Returns all fileinfos associated with a given blog.
        '''

        fileinfos_for_blog = FileInfo.select().where(FileInfo.template_mapping <<
            self.template_mappings.select(TemplateMapping.id))

        return fileinfos_for_blog


class Category(BaseModel):
    blog = ForeignKeyField(Blog, null=False, index=True)
    title = TextField()
    parent_category = IntegerField(default=None, null=True, index=True)
    default = BooleanField(default=False)

    @property
    def next_category(self):
        pass

    @property
    def previous_category(self):
        pass

class Page(BaseModel):

    title = TextField()
    type = IntegerField(default=0, index=True)  # 0 = regular blog post; 1 = standalone page
    path = EnforcedCharField(unique=True, null=True)  # only used if this is a standalone page
    external_path = EnforcedCharField(null=True, index=True)  # used for linking in an external file
    basename = TextField()
    user = ForeignKeyField(User, null=False, index=True)
    text = TextField()
    excerpt = TextField(null=True)
    blog = ForeignKeyField(Blog, null=False, index=True)
    created_date = DateTimeField(default=datetime.datetime.now)
    modified_date = DateTimeField(null=True)
    publication_date = DateTimeField(null=True, index=True)
    status = CharField(max_length=32, index=True, default=page_status.unpublished)
    tag_text = TextField(null=True)
    currently_edited_by = IntegerField(null=True)
    author = user

    @property
    def status_id(self):
        return page_status.id[self.status]

    @property
    def link_format(self):
        return '{}/page/{}/edit'.format(BASE_URL, self.id)

    @property
    def listing_id(self):
        return 'page_title_{}'.format(self.id)

    @property
    def paginated_text(self):
        paginated_text = self.text.split('<!-- pagebreak -->')
        return paginated_text

    @property
    def tags(self):
        tag_list = Tag.select().where(
            Tag.id << TagAssociation.select(TagAssociation.tag).where(
                TagAssociation.page == self)).order_by(Tag.tag)

        return tag_list

    @property
    def author(self):
        return self.user

    @property
    def revisions(self):
        revisions = PageRevision.select().where(PageRevision.page_id == self.id).order_by(PageRevision.modified_date.desc())

        return revisions

    @property
    def templates(self):
        '''
        Returns all page templates for this page.
        '''
        page_templates = Template.select().where(
            Template.blog == self.blog.id,
            Template.template_type == template_type.page)

        return page_templates


    @property
    def archives(self):
        '''
        Returns all date-based archives for this page.
        '''
        page_templates = Template.select().where(
            Template.blog == self.blog.id,
            Template.template_type == template_type.archive)

        return page_templates

    @property
    def archive_mappings(self):
        '''
        Returns mappings for all date-based archives for this page.
        '''
        archive_mappings = TemplateMapping.select().where(
            TemplateMapping.template << self.archives.select(Template.id).tuples(),
            TemplateMapping.archive_type in [2, 3])

        return archive_mappings

    @property
    def template_mappings(self):
        '''
        Returns all template mappings associated with page for this blog.
        '''

        template_mappings = TemplateMapping.select().where(
            TemplateMapping.template << self.templates.select(Template.id).tuples())

        return template_mappings


    @property
    def default_template_mapping(self):
        '''
        Returns the default template mapping associated with this page.
        '''

        t = TemplateMapping.get(TemplateMapping.is_default == True,
            TemplateMapping.template << self.templates.select(Template.id).tuples())

        template_mapping = self.publication_date.date().strftime(t.path_string)

        return template_mapping

    @property
    def fileinfos(self):
        '''
        Returns any fileinfo objects associated with this page.
        '''

        fileinfos = FileInfo.select().where(
            FileInfo.page == self)

        return fileinfos

    @property
    def default_fileinfo(self):
        '''
        Returns the default fileinfo associated with the page.
        Useful if you have pages that have multiple mappings.
        '''

        default_mapping = TemplateMapping.get(
            TemplateMapping.id << self.template_mappings,
            TemplateMapping.is_default == True)

        default_fileinfo = FileInfo.get(
            FileInfo.page == self,
            FileInfo.template_mapping == default_mapping)

        return default_fileinfo

    @property
    def permalink(self):

        if self.id is not None:
            f_info = self.default_fileinfo
            permalink = self.blog.url + "/" + f_info.file_path
        else:
            permalink = ""

        return permalink

    @property
    def preview_permalink(self):

        '''
        TODO: the behavior of this function is wrong
        in both local and remote mode,
        it should specify a link to a temporary file
        generated from the current draft for the sake of a preview.
        '''

        if self.status_id == page_status.published:

            if DESKTOP_MODE is True:

                tags = template_tags(page_id=self.id)

                preview_permalink = tpl(BASE_URL_ROOT + '/' +
                     self.default_template_mapping + "." +
                     self.blog.base_extension + "?_=" + str(self.blog.id), **tags.__dict__)
            else:
                preview_permalink = self.permalink

        else:
            preview_permalink = BASE_URL + "/page/" + str(self.id) + "/preview"

        return preview_permalink

    @property
    def categories(self):

        categories = PageCategory.select().where(PageCategory.page == self)

        return categories

    @property
    def primary_category(self):

        primary = self.categories.select().where(PageCategory.primary == True).get()

        return primary.category

    @property
    def media(self):
        '''
        Returns iterable of all Media types associated with an entry.
        '''

        media_association = MediaAssociation.select(MediaAssociation.id).where(
            MediaAssociation.page == self.id).tuples()

        media = Media.select().where(Media.id << media_association)

        return media

    @property
    def next_page(self):
        '''
        Returns the next published page in the blog, in ascending chronological order.
        '''

        try:

            next_page = self.blog.published_pages().select().where(
                Page.blog == self.blog,
                Page.publication_date > self.publication_date).order_by(
                Page.publication_date.asc(), Page.id.asc()).get()

        except Page.DoesNotExist:

            next_page = None

        return next_page

    @property
    def previous_page(self):
        '''
        Returns the previous published page in the blog, in descending chronological order.
        '''

        try:

            previous_page = self.blog.published_pages().select().where(
                Page.blog == self.blog,
                Page.publication_date < self.publication_date).order_by(
                Page.publication_date.desc(), Page.id.desc()).get()

        except Page.DoesNotExist:

            previous_page = None

        return previous_page

    @property
    def next_in_category(self):
        '''
        This returns a dictionary of categories associated with the current entry
        along with the next entry in that category
        This way we can say self.next_in_category[category_id], etc.
        '''
        pass

    @property
    def previous_in_category(self):
        pass

    def save(self, user, no_revision=False, backup_only=False, change_note=None):

        '''
        Wrapper for the model's .save() action, which also updates the
        PageRevision table to include a copy of the current revision of
        the page BEFORE the save is committed.
        '''
        from core.log import logger

        revision_save_result = None

        if no_revision == False and self.id is not None:
            page_revision = PageRevision.copy(self)
            revision_save_result = page_revision.save(user, self, False, change_note)

        page_save_result = Model.save(self) if backup_only is False else None


        if revision_save_result is not None:
            logger.info("Page {} edited by user {}.".format(
                self.for_log,
                user.for_log))

        else:
            logger.info("Page {} edited by user {} but without changes.".format(
                self.for_log,
                user.for_log))


        return (page_save_result, revision_save_result)

    revision_fields = {'id':'page_id'}

class RevisionMixin(object):
    @classmethod
    def copy(_class, source, **ka):

        instance = _class(**ka)
        subst = _class.revision_fields

        for name in source._meta.fields:

            value = getattr(source, name)
            target_name = subst[name] if name in subst else name
            setattr(instance, target_name, value)

        return instance

class PageRevision(Page, RevisionMixin):
    page_id = IntegerField(null=False)
    is_backup = BooleanField(default=False)
    change_note = TextField(null=True)
    saved_by = IntegerField(null=True)

    @property
    def saved_by_user(self):

        saved_by_user = get_user(user_id=self.saved_by)
        if saved_by_user is None:
            dead_user = User(name='Deleted user (ID #' + str(self.saved_by) + ')', id=saved_by_user)
            return dead_user
        else:
            return saved_by_user


    def save(self, user, current_revision, is_backup=False, change_note=None):

        from core.log import logger
        from core.error import PageNotChanged


        max_revisions = self.blog.max_revisions

        previous_revisions = (self.select().where(PageRevision.page_id == self.page_id)
            .order_by(PageRevision.modified_date.desc()).limit(max_revisions))

        if previous_revisions.count() > 0:

            last_revision = previous_revisions[0]

            page_changed = False

            for name in last_revision._meta.fields:
                if name not in ("modified_date", "id", "page_id", "is_backup", "change_note", "saved_by"):
                    value = getattr(current_revision, name)
                    new_value = getattr(last_revision, name)

                    if value != new_value:
                        page_changed = True
                        break

            if page_changed is False:
                raise PageNotChanged('Page {} was saved but without changes.'.format(
                    current_revision.for_log))


        if previous_revisions.count() >= max_revisions:

            older_revisions = DeleteQuery(PageRevision).where(PageRevision.page_id == self.page_id,
                PageRevision.modified_date < previous_revisions[max_revisions - 1].modified_date)

            older_revisions.execute()

        self.is_backup = is_backup
        self.change_note = change_note
        self.saved_by = user.id

        results = Model.save(self)

        logger.info("Revision {} for page {} created.".format(
            date_format(self.modified_date),
            self.for_log))

        return results


class PageCategory(BaseModel):

    page = ForeignKeyField(Page, null=False, index=True)
    category = ForeignKeyField(Category, null=False, index=True)
    primary = BooleanField(default=True)

    @property
    def next_in_category(self):

        pass

    @property
    def previous_in_category(self):

        pass


class System(BaseModel):
    pass

class KeyValue(BaseModel):

    object = CharField(max_length=64, null=False, index=True)  # table name
    objectid = IntegerField(null=True)
    key = EnforcedCharField(null=False, default="Key", index=True)
    value = TextField(null=True)
    parent = ForeignKeyField('self', null=True, index=True)
    is_schema = BooleanField(default=False)
    is_unique = BooleanField(default=False)
    value_type = CharField(max_length=64)


tag_template = '''
<span class='tag-block'><button {new} data-tag="{id}" id="tag_{id}" title="See tag details"
type="button" class="btn btn-{btn_type} btn-xs tag-title">{tag}</button><button id="tag_del_{id}"
data-tag="{id}" title="Remove tag" type="button" class="btn btn-{btn_type} btn-xs tag-remove"><span class="glyphicon glyphicon-remove"></span></button></span>
'''
tag_link_template = '''
<a class="tag_link" target="_blank" href="{url}">{tag}</a>'''

new_tag_template = '''
<span class="tag_link">{tag}</span>'''

class Tag(BaseModel):
    tag = TextField()
    blog = ForeignKeyField(Blog, null=False, index=True)
    is_hidden = BooleanField(default=False, index=True)

    @property
    def in_pages(self):

        tagged_pages = TagAssociation.select(TagAssociation.page).where(
            TagAssociation.tag == self).tuples()

        in_pages = Page.select().where(
            Page.id << tagged_pages)

        return in_pages

    @property
    def for_listing(self):

        template = tag_link_template.format(
            id=self.id,
            url=BASE_URL + "/blog/" + str(self.blog.id) + "/tag/" + str(self.id),
            tag=html_escape(self.tag))

        return template

    @property
    def for_display(self):

        btn_type = 'warning' if self.tag[0] == "@" else 'info'

        template = tag_template.format(
            id=self.id,
            btn_type=btn_type,
            new='',
            tag=tag_link_template.format(
                id=self.id,
                url=BASE_URL + "/blog/" + str(self.blog.id) + "/tag/" + str(self.id),
                tag=html_escape(self.tag))
            )

        return template

    @property
    def new_tag_for_display(self):

        btn_type = 'warning' if self.tag[0] == "@" else 'info'

        template = tag_template.format(
            id=0,
            tag=new_tag_template.format(
                tag=html_escape(self.tag)),
            btn_type=btn_type,
            new='data-new-tag="{}" '.format(html_escape(self.tag))
            )

        return template




class Template(BaseModel):
    title = TextField(default="Untitled Template", null=False)
    theme = ForeignKeyField(Theme, null=False, index=True)
    template_type = CharField(max_length=32, index=True, null=False)
    blog = ForeignKeyField(Blog, null=False, index=True)
    body = TextField(null=True)
    publishing_mode = CharField(max_length=32, index=True, null=False)
    external_path = TextField(null=True)  # used for linking in an external file
    modified_date = DateTimeField(default=datetime.datetime.now)
    is_include = BooleanField(default=False, null=True)

    def include(self, include_name):
        include = Template.get(Template.title == include_name,
            Template.theme == self.theme.id)
        return include.body

    @property
    def includes(self):
        # get most recent fileinfo for page
        # use that to compute includes
        # we may want to make that something we can control the context for
        pass

    @property
    def mappings(self):
        '''
        Returns all file mappings for the template.
        '''
        template_mappings = TemplateMapping.select().where(TemplateMapping.template == self)
        return template_mappings

    @property
    def fileinfos(self):
        '''
        Returns a list of all fileinfos associated with the selected template.
        '''
        fileinfos = FileInfo.select().where(
            FileInfo.template_mapping << self.mappings)
        return fileinfos

    @property
    def fileinfos_published(self):
        if self.template_type == "Page":
            return self.fileinfos.select().join(Page).where(
                Page.status == page_status.published)
        else:
            if self.publishing_mode != "Do not publish":
                return self.fileinfos



    @property
    def default_mapping(self):
        '''
        Returns the default file mapping for the template.
        '''
        default_mapping = TemplateMapping.select().where(TemplateMapping.template == self,
            TemplateMapping.is_default == True).get()
        return default_mapping


class TemplateMapping(BaseModel):

    template = ForeignKeyField(Template, null=False, index=True)
    is_default = BooleanField(default=False, null=True)
    path_string = TextField()
    archive_type = IntegerField()
    # 1 = Index
    # 2 = Page
    # 3 = Date-Based
    # TODO: I believe this was deprecated a long time ago
    archive_xref = CharField(max_length=16, null=True)
    modified_date = DateTimeField(default=datetime.datetime.now)

    '''
    def _build_xrefs(self):

        from core import cms
        cms.purge_fileinfos(self.fileinfos)

        import re
        iterable_tags = (
            (re.compile('%Y'), 'Y'),
            (re.compile('%m'), 'M'),
            (re.compile('%d'), 'D'),
            (re.compile('\{\{page\.categories\}\}'), 'C'),
            (re.compile('\{\{page\.primary_category.?[^\}]*\}\}'), 'C'),  # Not yet implemented
            (re.compile('\{\{page\.user.?[^\}]*\}\}'), 'A')
            (re.compile('\{\{page\.author.?[^\}]*\}\}'), 'A')
            )

        match_pos = []

        for tag, func in iterable_tags:
            match = tag.search(self.path_string)
            if match is not None:
                match_pos.append((func, match.start()))

        sorted_match_list = sorted(match_pos, key=lambda row: row[1])

        context_string = "".join(n for n, m in sorted_match_list)

        self.archive_xref = context_string

        content_type = self.template.template_type
        if content_type == 'Page':
            cms.build_pages_fileinfos(self.template.blog.pages())
        if content_type == 'Archive':
            cms.build_archives_fileinfos(self.template.blog.pages())
        if content_type == 'Index':
            cms.build_indexes_fileinfos(self.template.blog.index_templates())
    '''

    @property
    def fileinfos(self):
        '''
        Returns a list of all fileinfos associated with the selected template mapping.
        '''
        fileinfos = FileInfo.select().where(
            FileInfo.template_mapping == self)

        return fileinfos

    @property
    def next_in_mapping(self):
        '''
        Stub for the next archive entry for a given template.
        Determines from xref map.
        We should have the template mapping as part of a context as well.
        I don't think we do this yet.

        '''
        pass

    @property
    def previous_in_mapping(self):

        pass

##########################

class Media(BaseModel):
    filename = CharField(null=False)
    path = EnforcedCharField(unique=True)
    local_path = EnforcedCharField(unique=True, null=True)  # deprecated?
    # should eventually be used to calculate where on the local filesystem
    # the file is when we are running in desktop mode, but I think we may
    # be able to deduce that from other things

    url = EnforcedCharField(unique=True, null=True)
    type = CharField(max_length=32, index=True)
    created_date = DateTimeField(default=datetime.datetime.now)
    modified_date = DateTimeField(default=datetime.datetime.now)
    friendly_name = TextField(null=True)
    tag_text = TextField(null=True)
    user = ForeignKeyField(User, null=False)
    blog = ForeignKeyField(Blog, null=True)
    site = ForeignKeyField(Site, null=True)

    @property
    def name(self):
        return self.friendly_name

    @property
    def link_format(self):
        return "{}/blog/{}/media/{}/edit".format(
            BASE_URL, str(self.blog.id), self.id)

    @property
    def preview_url(self):
        '''
        In desktop mode, returns a preview_url
        otherwise, returns the mapped URL to the media
        as if it were being accessed through the site in question
        (assuming it can be found there)
        '''
        if DESKTOP_MODE:
            return BASE_URL + "/media/" + str(self.id)
        else:
            return self.url

    @property
    def associated_with(self):
        '''
        Returns a listing of all pages this media is associated with.
        '''
        associated_with = MediaAssociation.select().where(
            MediaAssociation.media == self)

        return associated_with

    @property
    def preview_for_listing(self):
        return '''
<a href="media/{}/edit"><img style="max-height:50px" src="{}"></a>'''.format(
    self.id, self.preview_url)


class MediaAssociation(BaseModel):

    media = ForeignKeyField(Media)
    page = ForeignKeyField(Page, null=True)
    blog = ForeignKeyField(Blog, null=True)
    site = ForeignKeyField(Site, null=True)

class TagAssociation(BaseModel):
    tag = ForeignKeyField(Tag, null=False, index=True)
    page = ForeignKeyField(Page, null=True, index=True)
    media = ForeignKeyField(Media, null=True, index=True)


class FileInfo(BaseModel):

    page = ForeignKeyField(Page, null=True, index=True)
    template_mapping = ForeignKeyField(TemplateMapping, null=False, index=True)
    file_path = EnforcedCharField(null=False)
    sitewide_file_path = EnforcedCharField(index=True, null=False, unique=True)
    url = EnforcedCharField(null=False, index=True, unique=True)
    modified_date = DateTimeField(default=datetime.datetime.now)

    @property
    def xref(self):
        xref = TemplateMapping.select().where(
            TemplateMapping.id == self.template_mapping).get()
        return xref

    @property
    def author(self):

        try:
            author = self.context.select().where(FileInfoContext.object == "A").get()
            author = author.ref
        except FileInfoContext.DoesNotExist:
            author = None
        return author

    @property
    def context(self):

        context = FileInfoContext.select().where(
            FileInfoContext.fileinfo == self).order_by(FileInfoContext.id.asc())

        return context

    @property
    def year(self):
        try:
            year = self.context.select().where(FileInfoContext.object == "Y").get()
            year = year.ref
        except FileInfoContext.DoesNotExist:
            year = None
        return year

    @property
    def month(self):

        try:
            month = self.context.select().where(FileInfoContext.object == "M").get()
            month = month.ref
        except FileInfoContext.DoesNotExist:
            month = None
        return month

    @property
    def category(self):

        try:
            category = self.context.select().where(FileInfoContext.object == "C").get()
            category = category.ref
        except FileInfoContext.DoesNotExist:
            category = None
        return category



class FileInfoContext(BaseModel):

    fileinfo = ForeignKeyField(FileInfo, null=False, index=True)
    object = CharField(max_length=1)
    ref = IntegerField(null=True)

class Queue(BaseModel):
    job_type = CharField(null=False, max_length=16, index=True)
    is_control = BooleanField(null=False, default=False, index=True)
    priority = IntegerField(default=9, index=True)
    data_string = TextField(null=True)
    data_integer = IntegerField(null=True, index=True)
    date_touched = DateTimeField(default=datetime.datetime.now)
    blog = ForeignKeyField(Blog, index=True, null=False)
    site = ForeignKeyField(Site, index=True, null=False)


class Permission(BaseModel):
    user = ForeignKeyField(User, index=True)
    permission = IntegerField(null=False)
    blog = ForeignKeyField(Blog, index=True, null=True)
    site = ForeignKeyField(Site, index=True, null=True)
    # sitewide settings ignore blog/site settings

class Plugin(BaseModel):

    name = TextField(null=False)
    friendly_name = TextField(null=False)
    path = TextField(null=False)
    priority = IntegerField(null=True, default=0)
    enabled = BooleanField(null=False, default=False)

    @property
    def _plugin_list(self):
        from core.plugins import plugin_list
        return plugin_list

    def _get_plugin_property(self, plugin_property, deactivated_message):
        if self.enabled is True:
            return self._plugin_list[self.name].__dict__[plugin_property]
        else:
            return deactivated_message

    @property
    def loaded_plugins(self):
        return self.plugin_list

    @property
    def description(self):
        return self._get_plugin_property('__plugin_description__', '[Not activated]')

    @property
    def version(self):
        return self._get_plugin_property('__version__', '')

    @property
    def _friendly_name(self):
        return self._get_plugin_property('__plugin_name__', '')

# TODO: make a template, entry revisions class that extends those base classes
# Templates includes things like varied templates for posts

def get_user(**ka):

    if 'user_id' in ka:
        try:
            user = User.get(User.id == ka['user_id'])
        except User.DoesNotExist:
            raise User.DoesNotExist('User #{} was not found.'.format(ka['user_id']))
        else:
            return user


def get_page(page_id):

    try:
        page = Page.get(Page.id == page_id)

    except Page.DoesNotExist as e:
        raise Page.DoesNotExist('Page {} does not exist'.format(page_id), e)

    return page

def get_template(template_id):

    try:
        template = Template.get(Template.id == template_id)
    except Template.DoesNotExist as e:
        raise Template.DoesNotExist('Template {} does not exist'.format(template_id), e)

    return template

def get_theme(theme_id):
    try:
        theme = Theme.get(Theme.id == theme_id)
    except Theme.DoesNotExist as e:
        raise Theme.DoesNotExist('Theme {} does not exist.'.format(theme_id), e)
    return theme

def get_blog(blog_id):

    try:
        blog = Blog.get(Blog.id == blog_id)
    except Blog.DoesNotExist as e:
        raise Blog.DoesNotExist('Blog {} does not exist'.format(blog_id), e)

    return blog

def get_site(site_id):

    try:
        site = Site.get(Site.id == site_id)
    except Site.DoesNotExist as e:
        raise Site.DoesNotExist('Site {} does not exist'.format(site_id), e)

    return site

def get_media(media_id, blog=None):
    try:
        media = Media.get(Media.id == media_id)
    except Media.DoesNotExist as e:
        raise Media.DoesNotExist ('Media element {} does not exist'.format(media_id), e)

    if blog:
        if media.blog != blog:
            raise MediaAssociation.DoesNotExist('Media #{} is not associated with blog {}'.format(media.id, blog.id))

    return media

def default_template_mapping(page):
    '''Returns the default template mapping for a given page,
    the one associated with its permalink.'''
    templates = Template.select().where(Template.template_type == template_type.page)
    t = TemplateMapping.get(TemplateMapping.is_default == True, TemplateMapping.template << templates)
    time_string = page.publication_date.date().strftime(t.path_string)
    return time_string


tags_init = ("blog", "page", "authors", "site", "user",
    "template", "archive")

class TemplateTags(object):
    # Class for the template tags that are used in page templates.
    # Also used for building many other things.

    def __init__(self, **ka):

        for key in tags_init:
            setattr(self, key, None)

        self.search_query, self.search_terms = '', ''
        self.request = request
        self.settings = _settings
        self.utils = _utils
        self.sites = Site.select()
        self.status_modes = page_status
        # self.media = get_media

        if 'search' in ka:
            if ka['search'] is not None:
                self.search_terms = ka['search']
                self.search_query = "&search=" + self.search_terms

        self.pages = ka.get('pages', None)
        self.status = ka.get('status', None)

        # self.media = ka.get('media', None)

        if 'user' in ka:
            self.user = ka['user']
            token = self.user.last_login
        else:
            token = SECRET_KEY

        self.csrf_token = csrf_tag(token)
        self.csrf = csrf_hash(token)

        if 'page_id' in ka:
            self.page = get_page(ka['page_id'])
            ka['page'] = self.page

        if 'page' in ka:
            self.page = ka['page']
            ka['blog_id'] = self.page.blog.id
            self.pages = (self.page,)

        if 'template_id' in ka:
            self.template = get_template(ka['template_id'])
            ka['blog_id'] = self.template.blog.id

        if 'blog_id' in ka:
            self.blog = get_blog(ka['blog_id'])
            ka['site_id'] = self.blog.site.id

        self.blog = ka.get('blog', self.blog)

        if 'site_id' in ka:
            self.site = get_site(ka['site_id'])

        if self.blog:
            self.queue = Queue.select().where(Queue.blog == self.blog)
        elif self.site:
            self.queue = Queue.select().where(Queue.site == self.site)
        else:
            self.queue = Queue.select()

        if 'archive' in ka:
            self.archive = Struct()
            setattr(self.archive, "pages", self.blog.pages(ka['archive']))

            # TODO: replace this with a proper fixed list of archive types!!
            for n in ('year', 'month', 'category', 'author'):
                setattr(self.archive, n, ka['archive_context'].__getattribute__(n))

        self.media = ka.get('media', None)

def template_tags(**ka):
    return TemplateTags(**ka)

