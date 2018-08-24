# -*- coding: utf-8 -*-
import logging
import uuid
import nbxmpp
import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gdk, GLib, GdkPixbuf, Pango

from nbxmpp import simplexml
from nbxmpp.protocol import JID
from gajim import dialogs
from gajim import gtkgui_helpers
from gajim.common import ged
from gajim.common import app
from gajim.common import connection
from gajim.plugins import GajimPlugin
from gajim.plugins.helpers import log_calls
import base64, os

# namespaces & logger
log = logging.getLogger('gajim.plugin_system.XabberGroupsPlugin')
XABBER_GC = 'http://xabber.com/protocol/groupchat'
XABBER_GC_invite = 'http://xabber.com/protocol/groupchat#invite'

# import tempfile
# dir = tempfile.gettempdir() + '/xabavatars'
dir = os.environ['HOME'] + '/xabavatars'
AVATARS_DIR = os.path.normpath(dir)
try:
    os.stat(AVATARS_DIR)
except:
    os.mkdir(AVATARS_DIR)

allowjids = []

def loadallowjid():
    try:
        with open(os.path.normpath(AVATARS_DIR + '/jids.txt')) as allowlist:
            array = [row.strip() for row in allowlist]
        return array
    except:
        return []

def addallowjid(jid):
    global allowjids
    if jid in allowjids:
        return False
    allowjids.append(jid)
    allowlist = open(os.path.normpath(AVATARS_DIR + '/jids.txt'), 'a')
    allowlist.write(jid + '\n')
    allowlist.close()
    allowjids = loadallowjid()
    return True

allowjids = loadallowjid()

class XabberGroupsPlugin(GajimPlugin):

    @log_calls('XabberGroupsPlugin')
    def init(self):
        self.is_active = True
        self.description = _('Adds support Xabber Groups.')
        self.config_dialog = None
        self.controls = {}
        self.history_window_control = None

        self.events_handlers = {
            'decrypted-message-received': (ged.PREGUI1, self._nec_decrypted_message_received),
            'raw-iq-received': (ged.CORE, self._nec_iq_received),
        }
        self.gui_extension_points = {
            'chat_control_base': (self.connect_with_chat_control,
                                       self.disconnect_from_chat_control),
            'print_real_text': (self.print_real_text, None),
            'roster_draw_contact': (self.connect_with_roster_draw_contact, None),
        }

    @staticmethod
    def is_groupchat(contact):
        if hasattr(contact, 'is_groupchat'):
            return contact.is_groupchat()
        return False

    @log_calls('XabberGroupsPlugin')
    def connect_with_roster_draw_contact(self, roster, jid, account, contact):
        renderer_num = 11 + roster.nb_ext_renderers
        if self.is_groupchat(contact):
            return
        child_iters = roster._get_contact_iter(jid, account, contact, roster.model)
        if not child_iters:
            return
        for iter_ in child_iters:
            if roster.model[iter_][renderer_num] is None and contact.jid in allowjids:
                pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_size(os.path.normpath(AVATARS_DIR+'/t.png'), 16, 16)
                roster.model[iter_][renderer_num] = pixbuf


# ==================================================================================================== #

    @log_calls('XabberGroupsPlugin')
    def base64_to_image(self, img_base64, filename):
        # decode base, return realpath
        dir = AVATARS_DIR
        try:
            os.stat(dir)
        except:
            os.mkdir(dir)
        imgdata = base64.b64decode(img_base64)
        realfilename = os.path.abspath(dir+'/'+filename+'.jpg')
        filename = dir+'/'+filename+'.jpg'
        with open(filename, 'wb') as f:
            f.write(imgdata)
            f.close()
        return(realfilename)

    @log_calls('XabberGroupsPlugin')
    def send_ask_for_rights(self, account, jid):
        return 'u have no rights, mazafaka'

    @log_calls('XabberGroupsPlugin')
    def _nec_iq_received(self, obj):
        try:
            # check is iq from xabber gc
            item = obj.stanza.getTag('pubsub').getTag('items').getTag('item')
            base64avatar = item.getTag('data', namespace='urn:xmpp:avatar:data').getData()
            id = item.getAttr('id')
            avatar_loc = self.base64_to_image(base64avatar, id)
            print(avatar_loc)
        except:
            return


    @log_calls('XabberGroupsPlugin')
    def _nec_decrypted_message_received(self, obj):
        '''
        get incoming messages, check it, do smth with them
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
        if not jid:
            jid = obj.stanza.getTag('invite', namespace=XABBER_GC).getTag('jid').getData()

        def on_ok():
            addallowjid(jid)
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
        reason = obj.stanza.getTag('invite', namespace=XABBER_GC).getTag('reason').getData()
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
        room = obj.jid
        addallowjid(room)
        name = obj.stanza.getTag('x', namespace=XABBER_GC).getTag('nickname').getData()
        userid = obj.stanza.getTag('x', namespace=XABBER_GC).getTag('id').getData()
        if not name:
            name = False
        message = obj.stanza.getTag('x', namespace=XABBER_GC).getTag('body').getData()
        id = None
        try:
            id = obj.stanza.getTag('x', namespace=XABBER_GC).getTag('metadata', namespace='urn:xmpp:avatar:metadata')
            id = id.getTag('info').getAttr('id')
        except: id = 'unknown'
        jid = None
        try:
            jid = obj.stanza.getTag('x', namespace=XABBER_GC).getTag('jid').getData()
        except: jid = 'unknown'
        role = obj.stanza.getTag('x', namespace=XABBER_GC).getTag('role').getData()
        badge = obj.stanza.getTag('x', namespace=XABBER_GC).getTag('badge').getData()

        obj.additional_data.update({'jid': jid,
                                    'nickname': name,
                                    'message': message,
                                    'id': userid,
                                    'av_id': id,
                                    'role': role,
                                    'badge': badge
                                    })


        account = None
        accounts = app.contacts.get_accounts()
        myjid = obj.stanza.getAttr('to')
        for acc in accounts:
            realjid = app.get_jid_from_account(acc)
            realjid = app.get_jid_without_resource(str(realjid))
            if myjid == realjid:
                account = acc


        if id != 'unknown' and account:
            self.send_call_single_avatar(account, room, userid, id)

    @log_calls('XabberGroupsPlugin')
    def send_call_single_avatar(self, account, room_jid, u_id, av_id):

        try:
            # error if avatar is not exist
            dir = AVATARS_DIR + '/' + av_id + '.jpg'
            k = open(os.path.normpath(dir))
        except:
            stanza_send = nbxmpp.Iq(to=room_jid, typ='get')
            stanza_send.setAttr('id', str(av_id))
            stanza_send.setTag('pubsub').setNamespace('http://jabber.org/protocol/pubsub')
            stanza_send.getTag('pubsub').setTagAttr('items', 'node', ('urn:xmpp:avatar:data#'+str(u_id)))
            stanza_send.getTag('pubsub').getTag('items').setTagAttr('item', 'id', str(av_id))
            app.connections[account].connection.send(stanza_send, now=True)


    @log_calls('XabberGroupsPlugin')
    def connect_with_chat_control(self, chat_control):
        account = chat_control.contact.account.name
        jid = chat_control.contact.jid
        if jid in allowjids:  # ask for rights if xgc if open chat control
            self.send_ask_for_rights(chat_control.contact, jid)
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
        self.default_avatar = os.path.join(os.path.dirname(os.path.abspath(__file__)), "default.jpg")
        # self.default_avatar = base64.encodestring(open(default_avatar, "rb").read())

        self.previous_message_from = None

        self.message_id = -1
        self.message_tags_props = []

        # styles
        self.nickname_color = self.textview.tv.get_buffer().create_tag("nickname", foreground="red")
        # self.nickname_color.set_property("weight", Pango.Weight.BOLD)
        self.nickname_color.set_property("size_points", 10)

        self.text_style = self.textview.tv.get_buffer().create_tag("message_text", size_points=8)
        self.text_style.set_property("left-margin", 32)

        self.info_style = self.textview.tv.get_buffer().create_tag("info_text", size_points=10)
        self.info_style.set_property("foreground", "grey")
        self.info_style.set_property("style", Pango.Style.ITALIC)
        self.info_style.set_property("left-margin", 64)

        self.rolestyle = self.textview.tv.get_buffer().create_tag("role_text", size_points=10)
        self.rolestyle.set_property("foreground", "black")

        self.badgestyle = self.textview.tv.get_buffer().create_tag("badge_text", size_points=8)
        self.badgestyle.set_property("foreground", "grey")

        self.pointer_cursor = self.textview.tv.get_buffer().create_tag("pointer_cursor")

        # =======================================work with messages========================================= #
        self.change_cursor = False
        self.connect_signals()

    def connect_signals(self):
        tag_table = self.textview.tv.get_buffer().get_tag_table()
        tag = tag_table.lookup("message_text")
        if tag:
            self.textview.tv.connect('motion_notify_event', self.on_textview_motion_notify_event)

    def on_textview_motion_notify_event(self, widget, event):
        # change cursor on the nicks
        pointer_x, pointer_y = self.textview.tv.get_window(
            Gtk.TextWindowType.TEXT).get_pointer()[1:3]
        x, y = self.textview.tv.window_to_buffer_coords(Gtk.TextWindowType.TEXT,
            pointer_x, pointer_y)
        tags = self.textview.tv.get_iter_at_location(x, y)[1].get_tags()

        if self.change_cursor:
            self.textview.tv.get_window(Gtk.TextWindowType.TEXT).set_cursor(
                Gdk.Cursor.new(Gdk.CursorType.XTERM))
            self.change_cursor = False
        for tag in tags:
            tag_table = self.textview.tv.get_buffer().get_tag_table()
            if tag == tag_table.lookup("pointer_cursor"):
                self.textview.tv.get_window(Gtk.TextWindowType.TEXT).set_cursor(
                    Gdk.Cursor.new(Gdk.CursorType.HAND2))
            self.change_cursor = True

    def interact_with_txt(self, texttag, widget, event, iter_, tagname, additional_data):
        if event.type == Gdk.EventType.BUTTON_PRESS and event.button.button == 1:
            # left mouse button clicked
            begin_iter = iter_.copy()
            # we get the begining of the tag
            while not begin_iter.begins_tag(texttag):
                begin_iter.backward_char()
            end_iter = iter_.copy()
            # we get the end of the tag
            while not end_iter.ends_tag(texttag):
                end_iter.forward_char()
            buffer_ = self.textview.tv.get_buffer()
            word = buffer_.get_text(begin_iter, end_iter, True)
            for message_data in self.message_tags_props:
                if message_data[0] == tagname:
                    tag_table = self.textview.tv.get_buffer().get_tag_table()
                    tag = tag_table.lookup(tagname)
                    if message_data[2] == False:
                        tag.set_property("background", "#FFAAAA")
                        message_data[2] = True
                        print(tagname)
                        print(additional_data)
                    else:
                        tag.set_property("background", "#FFFFFF")
                        message_data[2] = False


    # ================================================================================ #
    def deinit_handlers(self):
        # remove all register handlers on wigets, created by self.xml
        # to prevent circular references among objects
        for i in list(self.handlers.keys()):
            if self.handlers[i].handler_is_connected(i):
                self.handlers[i].disconnect(i)
            del self.handlers[i]

    def print_message(self, iter_, SAME_FROM, buffer_, nickname, message, role, badge, additional_data):
        if not SAME_FROM:
            # avatar
            avatar = None
            try:
                path = os.path.normpath(AVATARS_DIR+'/'+additional_data['av_id']+'.jpg')
                avatar = open(path)
                avatar = os.path.normpath(path)
            except:
                avatar = self.default_avatar
            avatar_placement = buffer_.create_mark(None, iter_, True)
            # add avatar to last message by link !!! FROM SOMEWHERE IN A COMPUTER !!! for now its default
            app.thread_interface(self._update_avatar, [avatar, avatar_placement, additional_data])

        all_message_start_iter = buffer_.create_mark(None, iter_, True)
        if not SAME_FROM:
            # nickname
            start_iter = buffer_.create_mark(None, iter_, True)
            buffer_.insert_interactive(iter_, nickname, len(nickname.encode('utf-8')), True)
            end_iter = buffer_.create_mark(None, iter_, True)
            buffer_.apply_tag(self.nickname_color, buffer_.get_iter_at_mark(start_iter), buffer_.get_iter_at_mark(end_iter))

            # badge
            badge = " "+badge
            start_iter = buffer_.create_mark(None, iter_, True)
            buffer_.insert_interactive(iter_, badge, len(badge.encode('utf-8')), True)
            end_iter = buffer_.create_mark(None, iter_, True)
            buffer_.apply_tag(self.badgestyle, buffer_.get_iter_at_mark(start_iter), buffer_.get_iter_at_mark(end_iter))

            # role
            role = " "+role
            start_iter = buffer_.create_mark(None, iter_, True)
            buffer_.insert_interactive(iter_, role, len(role.encode('utf-8')), True)
            end_iter = buffer_.create_mark(None, iter_, True)
            buffer_.apply_tag(self.rolestyle, buffer_.get_iter_at_mark(start_iter), buffer_.get_iter_at_mark(end_iter))

            buffer_.insert_interactive(iter_, '\n', len('\n'), True)

        # mark message with id
        self.message_id += 1
        tagname = "message_text_"+str(self.message_id)
        text_functional = self.textview.tv.get_buffer().create_tag(tagname)
        # def for text click
        text_functional.connect('event', self.interact_with_txt, tagname, additional_data)
        self.message_tags_props.append([tagname, additional_data, False])

        # message
        start_iter = buffer_.create_mark(None, iter_, True)
        buffer_.insert_interactive(iter_, message, len(message.encode('utf-8')), True)
        end_iter = buffer_.create_mark(None, iter_, True)
        # functional
        buffer_.apply_tag(text_functional, buffer_.get_iter_at_mark(all_message_start_iter), buffer_.get_iter_at_mark(end_iter))
        # visual
        buffer_.apply_tag(self.text_style, buffer_.get_iter_at_mark(start_iter), buffer_.get_iter_at_mark(end_iter))
        # pointer
        buffer_.apply_tag(self.pointer_cursor, buffer_.get_iter_at_mark(all_message_start_iter), buffer_.get_iter_at_mark(end_iter))

    def print_server_info(self, iter_, buffer_, info_message):
        start_iter = buffer_.create_mark(None, iter_, True)
        buffer_.insert_interactive(iter_, info_message, len(info_message.encode('utf-8')), True)
        buffer_.insert_interactive(iter_, '\n', len('\n'), True)
        end_iter = buffer_.create_mark(None, iter_, True)
        buffer_.apply_tag(self.info_style, buffer_.get_iter_at_mark(start_iter), buffer_.get_iter_at_mark(end_iter))


    def print_real_text(self, real_text, text_tags, graphics, iter_, additional_data):

        nickname = None
        user_id = None
        print(additional_data)

        if 'incomingtxt' in text_tags:
            if additional_data != {}:
                writer_jid = additional_data['jid']
                nickname = additional_data['nickname']
                message = additional_data['message']
                avatar_id = additional_data['av_id']
                user_id = additional_data['id']
                role = additional_data['role']
                badge = additional_data['badge']
            else:
                writer_jid = 'room'
                message = real_text

        if 'outgoingtxt' in text_tags:
            nickname = 'me'
            message = real_text
            role = ""
            badge = ""

        SAME_FROM = False
        IS_MSG = False
        # if nickname is exist
        if nickname:
            IS_MSG = True

        if 'outgoingtxt' in text_tags:
            if self.previous_message_from == 'me':
                SAME_FROM = True
            else:
                self.previous_message_from = 'me'
        if 'incomingtxt' in text_tags:
            if self.previous_message_from == user_id:
                SAME_FROM = True
            else:
                self.previous_message_from = user_id



        buffer_ = self.textview.tv.get_buffer()
        if not iter_:
            iter_ = buffer_.get_end_iter()

        # delete old "[time] name: "
        # if nickname:
        self.textview.plugin_modified = True
        lineindex = buffer_.get_line_count() - 1
        prevline = buffer_.get_iter_at_line(lineindex)
        buffer_.delete(prevline, iter_)

        if IS_MSG:
            self.print_message(iter_, SAME_FROM, buffer_, nickname, message, role, badge, additional_data)
        else:
            self.print_server_info(iter_, buffer_, real_text)

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

    def on_avatar_press_event(self, eb, event, additional_data):
        isme = False
        try: h = additional_data['nickname']
        except: isme = True

        def on_ok():
            return

        def on_cancel():
            return

        # right click
        if event.type == Gdk.EventType.BUTTON_PRESS and event.button == 3:
            if isme:
                dialog = dialogs.NonModalConfirmationDialog('hello', sectext='it is your avatar',
                    on_response_ok=on_ok, on_response_cancel=on_cancel)
                dialog.popup()
            else:
                pritext = _('user data')
                sectext = _('%(name)s  info. \n'
                            'name: %(name)s \n'
                            'role: %(role)s \n'
                            'jid: %(jid)s \n'
                            'id: %(id)s \n'
                            'avatar id: %(av_id)s \n'
                            'two buttons exist:') % {'name': additional_data['nickname'],
                                                     'role': additional_data['role'],
                                                     'jid': additional_data['jid'],
                                                     'id': additional_data['id'],
                                                     'av_id': additional_data['av_id']}
                dialog = dialogs.NonModalConfirmationDialog(pritext, sectext=sectext,
                    on_response_ok=on_ok, on_response_cancel=on_cancel)
                dialog.popup()

        # left klick
        elif event.type == Gdk.EventType.BUTTON_PRESS and event.button == 1:
            self.on_avatar_right_click(event, additional_data)

    def on_avatar_right_click(self, event, additional_data):
        return

    # Change mouse pointer to HAND2 when
    # mouse enter the eventbox with the image
    def on_enter_event(self, eb, event):
        self.textview.tv.get_window(
            Gtk.TextWindowType.TEXT).set_cursor(Gdk.Cursor(Gdk.CursorType.HAND2))

    # Change mouse pointer to default when mouse leaves the eventbox
    def on_leave_event(self, eb, event):
        self.textview.tv.get_window(
            Gtk.TextWindowType.TEXT).set_cursor(Gdk.Cursor(Gdk.CursorType.XTERM))

    def _update_avatar(self, pixbuf, repl_start, additional_data):

        event_box = Gtk.EventBox()
        event_box.connect('enter-notify-event', self.on_enter_event)
        event_box.connect('leave-notify-event', self.on_leave_event)
        event_box.connect('button-press-event', self.on_avatar_press_event, additional_data)

        pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(pixbuf, 32, 32, False)
        # pixbuf = base64.b64decode(pixbuf)
        # pixbuf = GdkPixbuf.Pixbuf.from_data(pixbuf)

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
                margin: 0px;
                border-radius: 0%;
                }'''
                # border-style: solid;
                # border-width: 1;
                gtkgui_helpers.add_css_to_widget(image, css)
                image.set_name('Xavatar')

                event_box.add(image)
                event_box.show_all()
                self.textview.tv.add_child_at_anchor(event_box, anchor)

                if at_end:
                    self._scroll_to_end()
            except Exception as ex:
                log.exception("Exception while loading image %s", ex)
            return False
        # add to mainloop --> make call threadsafe
        GLib.idle_add(add_to_textview)