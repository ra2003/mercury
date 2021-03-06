<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <meta http-equiv="X-UA-Compatible" content="IE=edge">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    % include('include/page_title.tpl')
    <link href="{{settings.BASE_URL}}{{settings.STATIC_PATH}}/css/bootstrap.min.css" rel="stylesheet">
    <link href="{{settings.BASE_URL}}{{settings.STATIC_PATH}}/css/custom.css" rel="stylesheet">
  </head>
  <body>
  
<nav id="menu_bar" class="navbar navbar-default" style="margin-bottom:8px">
  <div class="">
    <div class="navbar-header">
      <button type="button" class="navbar-toggle collapsed" data-toggle="collapse" data-target="#navbar-collapse">
        <span class="sr-only">Toggle navigation</span>
        <span class="icon-bar"></span>
        <span class="icon-bar"></span>
        <span class="icon-bar"></span>
      </button>
        <ul class="nav navbar-brand visible-xs">Mercury</ul>
    </div>
    
    <div class="collapse navbar-collapse" id="navbar-collapse">
        <ul class="nav navbar-text" style="margin-left:0">
            <span class="breadcrumb" style="padding:0;background-color:inherit;">
            {{!menu}}
            </span>
        </ul>
    
      <ul class="nav navbar-nav navbar-right navbar-compact">
             
        % if defined('search_context'):
        <li>
        <a title="Search" href="#" onclick="toggle_search();"><span class="glyphicon glyphicon-search"></span><span class="visible-xs-inline">&nbsp;&nbsp;Search</span></a>        
        </li>
        % end
        
        % include('queue/queue_counter_include2.tpl')
        
        % if blog:
        <li>
          <a title="See the published version of this blog" target="_blank" href="{{blog.permalink}}"><span class="glyphicon glyphicon-new-window"></span>
          <span class="visible-xs-inline">&nbsp;See published blog</span></a>
        </li>
        % elif site:
        <li>
          <a title="See the published version of this site" target="_blank" href="{{site.permalink}}"><span class="glyphicon glyphicon-new-window"></span>
          <span class="visible-xs-inline">&nbsp;See published site</span></a>
        </li>
        % end
        
        <li class="dropdown">
            <a href="#" class="dropdown-toggle" data-toggle="dropdown" role="button" aria-expanded="false">
            <span style='display:inline-block' class='overflow max-width'><span class='caret'></span> {{user.short_name}}</span>&nbsp;</a>
              <ul class="dropdown-menu" role="menu">
                <li><a href="{{settings.BASE_URL}}/me">Settings</a></li>
                <li><a href="{{settings.BASE_URL}}/logout?_={{user.logout_nonce}}">Log out</a></li>
              </ul>
        </li>      
      </ul>
    </div><!-- /.navbar-collapse -->
  </div><!-- /.container-fluid -->
</nav>

% if defined('search_context'):
<div id="search" class="col-xs-12" 
% if search_terms == '':
style="display: none"
% end
>
	<div class="alert alert-info alert-dismissible" role="alert">
		<button type="button" class="close" onclick="toggle_search();" aria-label="Close"><span aria-hidden="true">&times;</span></button>
		<form accept-charset="utf-8" action="{{search_context[0]['form_target'](search_context[1])}}" id="search_form" class="form-inline">
		  <div class="form-group">
		    <label for="search_text">{{search_context[0]['form_description']}}  </label>
		    <div class="input-group">
		      <input name="search" value="{{utils.utf8_escape(search_terms)}}" type="text" class="form-control input-sm" id="search_text" placeholder="{{search_context[0]['form_placeholder']}}">
		      <span onclick="clear_search();" class="input-group-addon">
                <span class="glyphicon glyphicon-remove"></span>                
		      </span>
		    </div>
		  </div>
		<button id="search_button" type="submit" class="btn btn-default btn-sm">Go</button>
		</form>
	</div>
</div>
% end