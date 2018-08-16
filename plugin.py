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
        myjid = obj.stanza.getAttr('to')
        myjid = app.get_jid_without_resource(str(myjid))
        newbody = obj.stanza.getTag('x', namespace=XABBER_GC).getTag('body')
        nickname = obj.stanza.getTag('x', namespace=XABBER_GC).getTag('nickname')


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

# TODO list of xabber groupchats

# TODO save avatars

# TODO открывать окно с данными о собеседнике групчата при нажатии на аватар

class Base(object):

    def __init__(self, plugin, textview):
        # recieve textview to work with
        self.plugin = plugin
        self.textview = textview
        self.handlers = {}
        self.prelatest_mark = None
        self.latest_mark = None
        self.default_avatar = '/home/maksim.batyatin/.local/share/gajim/plugins/groups_plugin/pics/default.jpg'

    def deinit_handlers(self):
        # remove all register handlers on wigets, created by self.xml
        # to prevent circular references among objects
        for i in list(self.handlers.keys()):
            if self.handlers[i].handler_is_connected(i):
                self.handlers[i].disconnect(i)
            del self.handlers[i]

    def print_real_text(self, real_text, text_tags, graphics, iter_, additional_data):

        buffer_ = self.textview.tv.get_buffer()
        if not iter_:
            iter_ = buffer_.get_end_iter()

        # Show [avatar] until avatar loaded. do we need it?
        ttt = buffer_.get_tag_table()
        repl_start = buffer_.create_mark(None, iter_, True)
        buffer_.insert_with_tags(iter_, '[avatar]',
                                 *[(ttt.lookup(t) if isinstance(t, str) else t) for t in ["url"]])
        repl_end = buffer_.create_mark(None, iter_, True)

        # add avatar to last message by link !!! FROM SOMEWHERE IN A COMPUTER !!! for now its default
        app.thread_interface(self._update_avatar, [self.default_avatar, repl_start, repl_end])


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

    def _update_avatar(self, pixbuf, repl_start, repl_end):

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
                buffer_.delete(iter_,
                               buffer_.get_iter_at_mark(repl_end))

                if at_end:
                    self._scroll_to_end()
            except Exception as ex:
                log.exception("Exception while loading xavatar %s", ex)
            return False
        # add to mainloop --> make call threadsafe
        GLib.idle_add(add_to_textview)