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
import base64, os

allowjids = ['4test2@xmppdev01.xabber.com']
avatardata = []

# namespaces & logger
log = logging.getLogger('gajim.plugin_system.XabberGroupsPlugin')
XABBER_GC = 'http://xabber.com/protocol/groupchat'
XABBER_GC_invite = 'http://xabber.com/protocol/groupchat#invite'


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
                                           self._nec_decrypted_message_received),
            'raw-iq-received': (ged.CORE,
                                            self._nec_iq_received)
        }
        self.gui_extension_points = {
            'chat_control_base': (self.connect_with_chat_control,
                                       self.disconnect_from_chat_control),
            'print_real_text': (self.print_real_text, None),
        }

    @staticmethod
    def base64_to_image(img_base64, filename):
        # decode base, return realpath
        imgdata = base64.b64decode(img_base64)
        realfilename = os.path.abspath(filename + '.jpg')
        filename = filename + '.jpg'
        with open(filename, 'wb') as f:
            f.write(imgdata)
        return (realfilename)

    @log_calls('XabberGroupsPlugin')
    def _nec_iq_received(self, obj):
        print('алярма, новй айкъю пришёль \n'*10)
        # check is iq from xabber gc
        id = obj.getAttr('id')
        items = obj.stanza.getTag('pubsub').getTag('items').getData()
        if items:
            base64avatar = items.getTag('data', namespace='urn:xmpp:avatar:data')
            avatar_loc = self.base64_to_image(base64avatar, id)
            print(avatar_loc)


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
        jid = obj.stanza.getTag('x', namespace=XABBER_GC).getTag('jid').getData()
        if not jid:
            jid = None
        room = obj.jid
        name = obj.stanza.getTag('x', namespace=XABBER_GC).getTag('nickname').getData()
        if not name:
            name = False
        message = obj.stanza.getTag('x', namespace=XABBER_GC).getTag('body').getData()
        id = ''
        try:
            id = obj.stanza.getTag('x', namespace=XABBER_GC).getTag('metadata', namespace='urn:xmpp:avatar:metadata')
            id = id.getTag('info').getAttr('id')
        except: id = 'unknown'
        role = obj.stanza.getTag('x', namespace=XABBER_GC).getTag('role').getData()
        badge = obj.stanza.getTag('x', namespace=XABBER_GC).getTag('badge').getData()

        obj.additional_data.update({'jid': jid,
                                    'nickname': name,
                                    'message': message,
                                    'av_id': id,
                                    'role': role,
                                    'badge': badge
                                    })

        # hotfix list with personal data
        # remake db
        ISEXIST = False
        print(avatardata)
        for avList in avatardata:
            if (avList[0] == jid) and (avList[1] == room) and (avList[2] == name):
                print("PERSON IS ALREADY EXIST")
                ISEXIST = True
        if not ISEXIST:
            avatardata.append([jid, room, name, id, role, badge])
            print("PERSON ADDED")

            # send request for avatars
            accounts = app.contacts.get_accounts()
            myjid = obj.stanza.getAttr('to')
            for account in accounts:
                realjid = app.get_jid_from_account(account)
                realjid = app.get_jid_without_resource(str(realjid))
                if myjid == realjid:
                    stanza_send = nbxmpp.Iq(to=room, typ='get', frm=realjid)
                    stanza_send.setAttr('id', str(id))
                    stanza_send.setTag('pubsub').setNamespace('http://jabber.org/protocol/pubsub')
                    stanza_send.getTag('pubsub').setTagAttr('items', 'node', ('urn:xmpp:avatar:data#'+jid))
                    stanza_send.getTag('pubsub').getTag('items').setTagAttr('item', 'id', str(id))
                    app.connections[account].connection.send(stanza_send, now=True)
                    return

        # TODO recieve data

        print('AVARATDATA')
        for avList in avatardata:
            print(avList)

        """
    @log_calls('XabberGroupsPlugin')
    def ask_for_single_avatar(self):
        return 
        <iq type='get' from='romeo@montague.it/home' to='mychat@capulet.it' id='retrieve1'>
          <pubsub xmlns='http://jabber.org/protocol/pubsub'>
            <items node='urn:xmpp:avatar:data#juliet@capulet.it'>
              <item id='74c4ecf80b09aa4f7c58f5563db80f8251289898'/>
            </items>
          </pubsub>
        </iq>
        
        
        <message from='mychat@capulet.it' to='romeo@montague.it'>
          <x xmlns='http://xabber.com/protocol/groupchat'>
            <user>
              <id>1lgfukgiyx3ged09</id>
              <jid>juliet@capulet.it</jid>
              <nickname>Juliet</nickname>
              <metadata xmlns='urn:xmpp:avatar:metadata'>
                <info
                  bytes='12345'
                  height='64'
                  id='74c4ecf80b09aa4f7c58f5563db80f8251289898'
                  type='image/png'
                  width='64' />
              </metadata>
            </user>
            <message>Go to the garden</message>
          </x>
          <body xml:lang='en'>Juliet:\nGo to the garden</body>
        </message>
        
        
        
        <message from='4test2@xmppdev01.xabber.com' to='devmuler@jabber.ru' type='chat' id='d95f0fd1-c9a4-44a6-ac7d-2392c508e2cc'>
        <x xmlns='http://xabber.com/protocol/groupchat'>
        <id>rhbxg9rjitipwzdu</id>
        <jid>maksim.batyatin@redsolution.com</jid>
        <badge/>
        <nickname>Batyatin Maksim</nickname>
        <role>owner</role>
        <metadata xmlns='urn:xmpp:avatar:metadata'>
        <info width='64' height='64' type='image/jpeg' id='6b1798ba95a83d0c80221f18a1b00d95a2fc2f7a' bytes='16022'/>
        </metadata>
        <body xmlns='urn:ietf:params:xml:ns:xmpp-streams' xml:lang=''>HELLOUUUUUUU</body>
        </x>
        <markable xmlns='urn:xmpp:chat-markers:0'/>
        <body xml:lang='en'>Batyatin Maksim: 
        HELLOUUUUUUU</body>
        </message>



        cursor = avatardatabase.DB.cursor()
        cursor.execute('''SELECT EXISTS(SELECT * from gcs where
        jid = ? and
        room = ? and
        name = ? );''', (str(jid), str(room), str(name)))
        #  пользователь существует в бд
        if cursor.fetchone():
            print("Found!\n"*50)

        # TODO FIX list of xabber groupchats
        else:
            # пользователя соответственно нема, записиваем его в бд
            cursor.execute("INSERT INTO gcs (jid, room, name, id, role, badge) "
                           "values (?, ?, ?, ?, ?, ?)", (jid, room, name, id, role, badge))
            print("Created!\n"*50)

            # TODO save avatars: base64 -> img
        """

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
        BASE_DIR = os.path.dirname(os.path.abspath(__file__))
        self.default_avatar = os.path.join(BASE_DIR, "default.jpg")
        # self.default_avatar = base64.encodestring(open(default_avatar, "rb").read())

        self.previous_message_from = None

        # styles
        self.nickname_color = self.textview.tv.get_buffer().create_tag("nickname", foreground="red")
        self.nickname_color.set_property("size_points", 10)

        self.text_style = self.textview.tv.get_buffer().create_tag("message_text", size_points=8)
        self.text_style.set_property("left-margin", 32)

        self.info_style = self.textview.tv.get_buffer().create_tag("info_text", size_points=10)
        self.info_style.set_property("foreground", "grey")
        self.info_style.set_property("left-margin", 64)

        self.rolestyle = self.textview.tv.get_buffer().create_tag("role_text", size_points=10)
        self.rolestyle.set_property("foreground", "black")

        self.badgestyle = self.textview.tv.get_buffer().create_tag("badge_text", size_points=8)
        self.badgestyle.set_property("foreground", "grey")

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
            avatar_placement = buffer_.create_mark(None, iter_, True)
            # add avatar to last message by link !!! FROM SOMEWHERE IN A COMPUTER !!! for now its default
            app.thread_interface(self._update_avatar, [self.default_avatar, avatar_placement, additional_data])

            # TODO открывать окно с данными о собеседнике групчата при нажатии на аватар

            # nickname
            start_iter = buffer_.create_mark(None, iter_, True)
            buffer_.insert_interactive(iter_, nickname, len(nickname), True)
            end_iter = buffer_.create_mark(None, iter_, True)
            buffer_.apply_tag(self.nickname_color, buffer_.get_iter_at_mark(start_iter), buffer_.get_iter_at_mark(end_iter))

            # role
            role = " "+role
            start_iter = buffer_.create_mark(None, iter_, True)
            buffer_.insert_interactive(iter_, role, len(role), True)
            end_iter = buffer_.create_mark(None, iter_, True)
            buffer_.apply_tag(self.rolestyle, buffer_.get_iter_at_mark(start_iter), buffer_.get_iter_at_mark(end_iter))

            # badge
            badge = " "+badge
            start_iter = buffer_.create_mark(None, iter_, True)
            buffer_.insert_interactive(iter_, badge, len(badge), True)
            end_iter = buffer_.create_mark(None, iter_, True)
            buffer_.apply_tag(self.badgestyle, buffer_.get_iter_at_mark(start_iter), buffer_.get_iter_at_mark(end_iter))

            buffer_.insert_interactive(iter_, '\n', len('\n'), True)

        # message
        start_iter = buffer_.create_mark(None, iter_, True)
        buffer_.insert_interactive(iter_, message, len(message), True)
        end_iter = buffer_.create_mark(None, iter_, True)
        buffer_.apply_tag(self.text_style, buffer_.get_iter_at_mark(start_iter), buffer_.get_iter_at_mark(end_iter))

    def print_server_info(self, iter_, buffer_, info_message):
        buffer_.insert_interactive(iter_, '\n', len('\n'), True)
        start_iter = buffer_.create_mark(None, iter_, True)
        buffer_.insert_interactive(iter_, info_message, len(info_message), True)
        end_iter = buffer_.create_mark(None, iter_, True)
        buffer_.apply_tag(self.info_style, buffer_.get_iter_at_mark(start_iter), buffer_.get_iter_at_mark(end_iter))


    def print_real_text(self, real_text, text_tags, graphics, iter_, additional_data):



        print("additional data ok da")
        print(additional_data)
        print(type(additional_data))

        if 'incomingtxt' in text_tags:
            writer_jid = additional_data['jid']
            nickname = additional_data['nickname']
            message = additional_data['message']
            avatar_id = additional_data['av_id']
            role = additional_data['role']
            badge = additional_data['badge']

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
            if self.previous_message_from == writer_jid:
                SAME_FROM = True
            else:
                self.previous_message_from = writer_jid



        buffer_ = self.textview.tv.get_buffer()
        if not iter_:
            iter_ = buffer_.get_end_iter()

        # delete old "[time] name: "
        if nickname:
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

    def on_button_press_event(self, pr, gl, hf):
        print(pr)

    def _update_avatar(self, pixbuf, repl_start, additional_data):

        event_box = Gtk.EventBox()
        event_box.connect('button-press-event', self.on_button_press_event, "TRIGGERED!!!!")
        pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(pixbuf, 32, 32, True)
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
                box-shadow: 0px 0px 3px 0px alpha(@theme_text_color, 0.2);
                margin: 0px;
                border-radius: 16;
                border-style: solid;
                border-width: 1;
                }'''
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