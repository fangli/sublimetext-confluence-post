#!/usr/bin/env python
# -*- coding:utf-8 -*-


import sublime
import sublime_plugin
import re
from xmlrpclib import ServerProxy
import socket


def convert_markdown_to_html(content):
    try:
        import markdown2
    except:
        sublime.message_dialog('markdown2 not installed, using "sudo easy_install markdown2" and restart sublime')
    return markdown2.markdown(content).encode('utf8')


def convert_to_html(content, syntax, file_name):
    if syntax == "Markdown":
        return convert_markdown_to_html(content)
    try:
        from pygments import highlight
        from pygments.formatters import HtmlFormatter
        from pygments.lexers import (get_lexer_by_name, get_lexer_for_filename)
    except:
        sublime.message_dialog('Pygments not installed, using "sudo easy_install Pygments" and restart sublime')
        raise("Pygments not installed")

    try:
        lexer = get_lexer_by_name(syntax.lower(), stripall=True)
    except:
        lexer = None

    if lexer is None:
        try:
            lexer = get_lexer_for_filename(file_name, content, stripall=True)
        except:
            sublime.message_dialog('We don\'t know the syntax type for ' + syntax)
            raise

    formatter = HtmlFormatter(linenos=True, cssclass="source", noclasses=True)
    return highlight(content, lexer, formatter)


class ConfluencePostCommand(sublime_plugin.TextCommand):

    def __init__(self, view):
        self.view = view

    def to_html(self, content):
        syntax = self.view.settings().get('syntax')
        syntax = syntax.split('.')[0].split('/')[-1]
        view = sublime.Window.active_view(sublime.active_window())

        html_content = convert_to_html(content, syntax, view.file_name())
        return html_content

    def get_meta_and_content(self, contents):
        meta = dict()
        content = list()
        tmp = contents.splitlines()
        for x, entry in enumerate(tmp):
            if entry.strip():
                if re.match(r'#[Ss]pace: *', entry):
                    meta['space'] = re.sub('[^:]*: *', '', entry)
                elif re.match(r'#[Pp]arent: *', entry):
                    meta['parent_title'] = re.sub('[^:]*: *', '', entry)
                elif re.match(r'#[Tt]itle: *', entry):
                    meta['title'] = re.sub('[^:]*: *', '', entry)
            else:
                content = tmp[x+1:]
                break
        return meta, content

    def get_token(self, username, password):
        token = self.serv.confluence2.login(username, password)
        return token

    def get_page_by_title(self, token, space, title):
        try:
            page = self.serv.confluence2.getPage(token, space, title)
            return page
        except:
            return

    def store_page(self, token, space, parent_title, title, content):
        parent_page = self.get_page_by_title(token, space, parent_title)
        try:
            parent_id = parent_page['id']
        except TypeError:
            sublime.status_message('space not exist')
            raise
        page = self.get_page_by_title(token, space, title)
        if page:
            page['parentId'] = parent_id
            page['content'] = content
        else:
            page = dict(
                content=content, parentId=parent_id, space=space, title=title)
        self.serv.confluence2.storePage(token, page)
        result = self.serv.confluence2.getPage(token, space, title)
        sublime.message_dialog(result['url'])
        return

    def run(self, edit):
        # self.get_syntax()
        region = sublime.Region(0, self.view.size())
        contents = self.view.substr(region)
        meta, content = self.get_meta_and_content(contents)
        new_content = self.to_html('\n'.join(content))
        if not new_content:
            return

        settings = sublime.load_settings('MarkupJiraConfluence.sublime-settings')
        confluence_url = settings.get('confluence_url')
        username = settings.get('confluence_username')
        password = settings.get('confluence_password')
        socket.setdefaulttimeout(10)
        sublime.status_message('posting...')
        self.serv = ServerProxy(confluence_url)
        token = self.get_token(username, password)
        space = meta.get('space')
        parent_title = meta.get('parent_title')
        title = meta.get('title')
        self.store_page(token, space, parent_title, title, new_content)
