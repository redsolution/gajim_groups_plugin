# -*- coding: utf-8 -*-
import logging
import uuid
import nbxmpp
from gi.repository import Gtk, Gdk, GLib, GdkPixbuf

from nbxmpp import simplexml
from nbxmpp.protocol import JID
from gajim import dialogs
from gajim import gtkgui_helpers
from gajim.common import ged
from gajim.common import app
from gajim.common import connection
from gajim.plugins import GajimPlugin
from gajim.plugins.helpers import log_calls
import os.path
import sqlite3

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
db_path = os.path.join(BASE_DIR, ".local/share/gajim/plugins/groups_plugin/xabbergc.db")
DB = sqlite3.connect(db_path)

log = logging.getLogger('gajim.plugin_system.XabberGroupsPlugin')
# namespaces
XABBER_GC = 'http://xabber.com/protocol/groupchat'
allowjids = ['4test2@xmppdev01.xabber.com']

class XabberGroupsPlugin(GajimPlugin):

    @log_calls('XabberGroupsPlugin')
    def init(self):
        self.is_active = True
        self.description = _('Adds support Xabber Groups.')
        self.config_dialog = None
        self.controls = {}
        self.history_window_control = None

        self.events_handlers = {
            'decrypted-message-received': (ged.PREGUI1,
                                           self._nec_decrypted_message_received)}
        self.gui_extension_points = {
            'chat_control_base': (self.connect_with_chat_control,
                                       self.disconnect_from_chat_control),
            'print_real_text': (self.print_real_text, None),
        }

    @log_calls('XabberGroupsPlugin')
    def _nec_decrypted_message_received(self, obj):
        '''
        get incoming message, check it, do smth with them
        '''
        cr_invite = obj.stanza.getTag('invite', namespace=XABBER_GC)
        cr_message = obj.stanza.getTag('x', namespace=XABBER_GC)
        if cr_invite:
            self.invite_to_chatroom_recieved(obj)
        elif cr_message:
            self.xabber_message_recieved(obj)


    @log_calls('XabberGroupsPlugin')
    def invite_to_chatroom_recieved(self, obj):  
        myjid = obj.stanza.getAttr('to')
        myjid = app.get_jid_without_resource(str(myjid))
        jid = obj.stanza.getTag('invite', namespace=XABBER_GC).getAttr('jid')

        def on_ok():
            accounts = app.contacts.get_accounts()

            for account in accounts:
                realjid = app.get_jid_from_account(account)
                realjid = app.get_jid_without_resource(str(realjid))
                if myjid == realjid:
                    stanza_send = nbxmpp.Presence(to=jid, typ='subscribe', frm=realjid)
                    app.connections[account].connection.send(stanza_send, now=True)
                    return
            return

        def on_cancel():
            return

        name = obj.jid
        reason = obj.stanza.getTag('reason', namespace = XABBER_GC )
        pritext = _('invitation to xabber-chatroom')
        sectext = _('%(name)s  invites you to xabber chatroom. \n'
                    'Room: %(jid)s \n'
                    'Reason: %(reason)s \n'
                    'Do you want to accept?') % {'name': name, 'reason': reason, 'jid': jid}
        dialog = dialogs.NonModalConfirmationDialog(pritext, sectext=sectext,
            on_response_ok=on_ok, on_response_cancel=on_cancel)
        dialog.popup()

    @log_calls('XabberGroupsPlugin')
    def xabber_message_recieved(self, obj):
        jid = obj.stanza.getTag('x', namespace=XABBER_GC).getTag('jid')
        room = obj.jid
        name = obj.stanza.getTag('x', namespace=XABBER_GC).getTag('nickname')
        id = obj.stanza.getTag('x', namespace=XABBER_GC).getTag('id')
        role = obj.stanza.getTag('x', namespace=XABBER_GC).getTag('role')
        badge = obj.stanza.getTag('x', namespace=XABBER_GC).getTag('badge')

        cursor = DB.cursor()
        cursor.execute("SELECT EXISTS(SELECT * from gcs where jid = ? and room = ? and name = ? )", (jid, room, name))
        #  пользователь существует в бд
        if cursor.fetchone():
            print("Found!")
        # пользователя соответственно нема, записиваем его в бд

        # TODO FIX list of xabber groupchats
        else:
            cursor.execute("INSERT INTO gcs (jid, room, name, id, role, badge) "
                           "values (?, ?, ?, ?, ?, ?)", (jid, room, name, id, role, badge))
            print("Created!")

            # TODO save avatars: base64 -> img

    @log_calls('XabberGroupsPlugin')
    def connect_with_chat_control(self, chat_control):
        account = chat_control.contact.account.name
        jid = chat_control.contact.jid
        if account not in self.controls and jid in allowjids:
            self.controls[account] = {}
        self.controls[account][jid] = Base(self, chat_control.conv_textview)

    @log_calls('XabberGroupsPlugin')
    def disconnect_from_chat_control(self, chat_control):
        account = chat_control.contact.account.name
        jid = chat_control.contact.jid
        self.controls[account][jid].deinit_handlers()
        del self.controls[account][jid]

    @log_calls('UrlImagePreviewPlugin')
    def connect_with_history(self, history_window):
        if self.history_window_control:
            self.history_window_control.deinit_handlers()
        self.history_window_control = Base(
            self, history_window.history_textview)

    @log_calls('UrlImagePreviewPlugin')
    def disconnect_from_history(self, history_window):
        if self.history_window_control:
            self.history_window_control.deinit_handlers()
        self.history_window_control = None


    def print_real_text(self, tv, real_text, text_tags, graphics,
                        iter_, additional_data):
        if tv.used_in_history_window and self.history_window_control:
            self.history_window_control.print_real_text(
                real_text, text_tags, graphics, iter_, additional_data)

        account = tv.account
        for jid in self.controls[account]:
            if self.controls[account][jid].textview != tv or jid not in allowjids:
                continue
            self.controls[account][jid].print_real_text(
                real_text, text_tags, graphics, iter_, additional_data)
            return



class Base(object):

    def __init__(self, plugin, textview):
        # recieve textview to work with
        self.plugin = plugin
        self.textview = textview
        self.handlers = {}
        self.default_avatar = '.local/share/gajim/plugins/groups_plugin/pics/default.jpg'
        self.previous_message_from = ':'
        # styles
        self.nickname_color = self.textview.tv.get_buffer().create_tag("nickname", foreground="red")
        self.nickname_color.set_property("size_points", 10)
        self.text_style = self.textview.tv.get_buffer().create_tag("message_text", size_points=8)
        self.text_style.set_property("left-margin", 32)

    def deinit_handlers(self):
        # remove all register handlers on wigets, created by self.xml
        # to prevent circular references among objects
        for i in list(self.handlers.keys()):
            if self.handlers[i].handler_is_connected(i):
                self.handlers[i].disconnect(i)
            del self.handlers[i]

    def print_real_text(self, real_text, text_tags, graphics, iter_, additional_data):

        print(text_tags)
        print(additional_data)

        self.textview.plugin_modified = True
        SAME_FROM = False
        nickname = ''
        message = ''

        # split person name and messasge
        if 'incomingtxt' in text_tags:
            splittext = real_text.partition(':')
            nickname = splittext[0]+':'
            message = '\n'+splittext[2].replace('\n', '')
        elif 'outgoingtxt' in text_tags:
            nickname = 'me:'
            message = '\n'+real_text

        # check if new message is from same person
        if nickname == 'me:':
            if self.previous_message_from == None:
                SAME_FROM = True
            self.previous_message_from = None
        elif self.previous_message_from == nickname:
            SAME_FROM = True
        else:
            self.previous_message_from = nickname



        buffer_ = self.textview.tv.get_buffer()
        if not iter_:
            iter_ = buffer_.get_end_iter()

        lineindex = buffer_.get_line_count() - 1
        prevline = buffer_.get_iter_at_line(lineindex)
        buffer_.delete(prevline, iter_)

        if not SAME_FROM:
            # avatar
            repl_start = buffer_.create_mark(None, iter_, True)
            # add avatar to last message by link !!! FROM SOMEWHERE IN A COMPUTER !!! for now its default
            app.thread_interface(self._update_avatar, [self.default_avatar, repl_start])

            # TODO открывать окно с данными о собеседнике групчата при нажатии на аватар

            # nickname
            start_iter = buffer_.create_mark(None, iter_, True)
            buffer_.insert_interactive(iter_, nickname, len(nickname), True)
            end_iter = buffer_.create_mark(None, iter_, True)
            buffer_.apply_tag(self.nickname_color, buffer_.get_iter_at_mark(start_iter), buffer_.get_iter_at_mark(end_iter))

        # message
        start_iter = buffer_.create_mark(None, iter_, True)
        buffer_.insert_interactive(iter_, message, len(message), True)
        end_iter = buffer_.create_mark(None, iter_, True)
        buffer_.apply_tag(self.text_style, buffer_.get_iter_at_mark(start_iter), buffer_.get_iter_at_mark(end_iter))

        # TODO fix cyrillic

    def _get_at_end(self):
        try:
            # Gajim 1.0.0
            return self.textview.at_the_end()
        except AttributeError:
            # Gajim 1.0.1
            return self.textview.autoscroll

    def _scroll_to_end(self):
        try:
            # Gajim 1.0.0
            self.textview.scroll_to_end_iter()
        except AttributeError:
            # Gajim 1.0.1
            self.textview.scroll_to_end()

    def _update_avatar(self, pixbuf, repl_start):

        event_box = Gtk.EventBox()
        pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(pixbuf, 32, 32, True)

        def add_to_textview():
            try:
                at_end = self._get_at_end()

                buffer_ = repl_start.get_buffer()
                iter_ = buffer_.get_iter_at_mark(repl_start)
                buffer_.insert(iter_, "\n")
                anchor = buffer_.create_child_anchor(iter_)

                if isinstance(pixbuf, GdkPixbuf.PixbufAnimation):
                    image = Gtk.Image.new_from_animation(pixbuf)
                else:
                    image = Gtk.Image.new_from_pixbuf(pixbuf)

                css = '''#Xavatar {
                box-shadow: 0px 0px 3px 0px alpha(@theme_text_color, 0.2);
                margin: 0px;
                }'''
                gtkgui_helpers.add_css_to_widget(image, css)
                image.set_name('Xavatar')

                event_box.add(image)
                event_box.show_all()
                self.textview.tv.add_child_at_anchor(event_box, anchor)

                if at_end:
                    self._scroll_to_end()
            except Exception as ex:
                log.exception("Exception while loading xavatar %s", ex)
            return False
        # add to mainloop --> make call threadsafe
        GLib.idle_add(add_to_textview)