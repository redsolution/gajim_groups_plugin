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
        }

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


        # TODO check for forwarding
        forwarded = obj.stanza.getTag('forwarded', namespace='urn:xmpp:forward:0')
        forward_m = None
        if forwarded:
            print('forwarded\n'*10)
            delay = forwarded.getTag('delay', namespace='urn:xmpp:delay').getAttr('stamp')
            fobj = forwarded.getTag('message')

            fname = ''
            try: fname = fobj.getTag('x', namespace=XABBER_GC).getTag('nickname').getData()
            except: fname = name

            fuserid = ''
            try: fuserid = fobj.getTag('x', namespace=XABBER_GC).getTag('id').getData()
            except:
                fuserid = userid

            fmessage = ''
            try: fmessage = fobj.getTag('x', namespace=XABBER_GC).getTag('body').getData()
            except: fmessage = fobj.getTag('body').getData()

            fjid = None
            try:
                fjid = fobj.getTag('x', namespace=XABBER_GC).getTag('jid').getData()
            except:
                if fname == name:
                    fjid = jid
                else:
                    fjid = 'unknown'

            # TODO get avatar id from forward message
            fid = None
            try:
                fid = fobj.getTag('x', namespace=XABBER_GC).getTag('metadata',
                                                                   namespace='urn:xmpp:avatar:metadata').getTag(
                    'info').getAttr('id')
            except:
                if fuserid == userid:
                    fid = id
                else:
                    fid = 'unknown'

            try:
                frole = fobj.getTag('x', namespace=XABBER_GC).getTag('role').getData()
                fbadge = fobj.getTag('x', namespace=XABBER_GC).getTag('badge').getData()
            except:
                frole = role
                fbadge = badge

            forward_m = {'jid': fjid,
                        'nickname': fname,
                        'message': fmessage,
                        'id': fuserid,
                        'av_id': fid,
                        'role': frole,
                        'badge': fbadge
            }

        obj.additional_data.update({'jid': jid,
                                    'nickname': name,
                                    'message': message,
                                    'id': userid,
                                    'av_id': id,
                                    'role': role,
                                    'badge': badge,
                                    'forward': forward_m
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

        self.messages_ids = []

        self.box = Gtk.Box(False, 0, orientation=Gtk.Orientation.VERTICAL)
        self.box.set_halign(Gtk.Align.FILL)
        self.box.set_hexpand(True)
        self.box.set_vexpand(False)

        self.scrolled = Gtk.ScrolledWindow()
        self.scrolled.add(self.box)



        self.textview.tv.connect_after('size-allocate', self.resize)

        self.scrolled.size_allocate(self.textview.tv.get_allocation())
        # expand in textview doesnt work
        self.textview.tv.add(self.scrolled)

    def resize(self, widget, r):
        self.scrolled.set_size_request(r.width, r.height)
        messages = [m for m in self.box.get_children()]
        for i in messages:
            j = i.get_children()
            j[1].set_size_request(r.width - (64+95), -1)

            # in case of only grid
            # j = i.get_children()
            # j[1].set_size_request(r.width - (64+95), -1)

    def deinit_handlers(self):
        # remove all register handlers on wigets, created by self.xml
        # to prevent circular references among objects
        for i in list(self.handlers.keys()):
            if self.handlers[i].handler_is_connected(i):
                self.handlers[i].disconnect(i)
            del self.handlers[i]


    def print_message(self, iter_, SAME_FROM, buffer_, nickname, message, role, badge, additional_data):

        IS_FORWARD = False
        forward = None
        try:
            forward = additional_data['forward']
            if forward != None:
                IS_FORWARD = True
        except: forward = None

        # get avatars
        file = ''
        file2 = ''
        try:
            path = os.path.normpath(AVATARS_DIR + '/' + additional_data['av_id'] + '.jpg')
            file = open(path)
            file = os.path.normpath(path)
        except:
            file = self.default_avatar

        if IS_FORWARD:
            try:
                path2 = os.path.normpath(AVATARS_DIR + '/' + forward['av_id'] + '.jpg')
                file2 = open(path2)
                file2 = os.path.normpath(path2)
            except:
                file2 = self.default_avatar

        show = Gtk.Grid()
        show2 = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        show2.set_homogeneous(False)
        show3 = Gtk.Grid()
        simplegrid = Gtk.Grid()
        simplegrid.attach(show, 0, 0, 1, 1)
        simplegrid.attach(show2, 1, 0, 1, 1)
        simplegrid.attach(show3, 2, 0, 1, 1)
        simplegrid.set_size_request(300, -1)
        css = '''#messagegrid {
        margin: 10px 0px;}'''
        gtkgui_helpers.add_css_to_widget(simplegrid, css)
        simplegrid.set_name('messagegrid')
        self.box.add(simplegrid)

        # SHOW1
        pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(file, 32, 32, False)
        image = Gtk.Image.new_from_pixbuf(pixbuf)
        css = '''#xavatar {
        margin: 0px 16px;}'''
        gtkgui_helpers.add_css_to_widget(image, css)
        image.set_name('xavatar')
        avatar_event_box = Gtk.EventBox()
        avatar_event_box.connect('button-press-event', self.on_avatar_press_event, additional_data)
        avatar_event_box.connect('enter-notify-event', self.on_enter_event)
        avatar_event_box.connect('leave-notify-event', self.on_leave_event)
        if not SAME_FROM:
            avatar_event_box.add(image)
        show.add(avatar_event_box)

        if not SAME_FROM:
            # SHOW2
            name_badge_role = Gtk.Label()
            name_badge_role.set_markup('<span font_desc=\'12px\' color=\'#D32F2F\'>%(name)s</span> '
                                       '<span font_desc=\'12px\' color=\'black\'>%(badge)s</span> '
                                       '<span font_desc=\'10px\' color=\'grey\'><small>%(role)s</small></span>'
                                       '' % {'name': nickname,
                                             'badge': badge,
                                             'role': role})
            name_badge_role.set_line_wrap(True)
            name_badge_role.set_justify(Gtk.Justification.LEFT)
            name_badge_role.set_halign(Gtk.Align.START)
            css = '''#name_badge_role {
            margin-bottom: 6px;}'''
            gtkgui_helpers.add_css_to_widget(name_badge_role, css)
            name_badge_role.set_name('name_badge_role')
        if IS_FORWARD:
            pixbuf2 = GdkPixbuf.Pixbuf.new_from_file_at_scale(file2, 32, 32, False)
            image2 = Gtk.Image.new_from_pixbuf(pixbuf2)
            css = '''#xavatar-forward {
            margin: 0px 8px;}'''
            gtkgui_helpers.add_css_to_widget(image2, css)
            image2.set_name('xavatar-forward')

            avatar2_event_box = Gtk.EventBox()
            avatar2_event_box.connect('button-press-event', self.on_avatar_press_event, forward)
            avatar2_event_box.add(image2)


            show_forward_av = Gtk.Grid()
            show_forward_av.add(avatar2_event_box)

            name_badge_role2 = Gtk.Label()
            name_badge_role2.set_markup('<span font_desc=\'12px\' color=\'#D32F2F\'>%(name)s</span> '
                                        '<span font_desc=\'12px\' color=\'black\'>%(badge)s</span> '
                                        '<span font_desc=\'10px\' color=\'grey\'><small>%(role)s</small></span>'
                                        '' % {'name': forward['nickname'],
                                              'badge': forward['badge'],
                                              'role': forward['role']})
            name_badge_role2.set_line_wrap(True)
            name_badge_role2.set_justify(Gtk.Justification.LEFT)
            name_badge_role2.set_halign(Gtk.Align.START)
            css = '''#name_badge_role {
            margin-bottom: 6px;}'''
            gtkgui_helpers.add_css_to_widget(name_badge_role2, css)
            name_badge_role2.set_name('name_badge_role')

            messagetext = Gtk.Label()
            css = '''#message_font_size {
            font-size: 12px;}'''
            gtkgui_helpers.add_css_to_widget(messagetext, css)
            messagetext.set_name('message_font_size')
            messagetext.set_text(forward['message'])
            messagetext.set_line_wrap(True)
            messagetext.set_justify(Gtk.Justification.LEFT)
            messagetext.set_halign(Gtk.Align.START)

            message_data_container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
            message_data_container.set_homogeneous(False)
            message_data_container.pack_start(name_badge_role2, True, True, 0)
            message_data_container.pack_start(messagetext, True, True, 0)

            messagecontainer = Gtk.Grid()
            messagecontainer.attach(show_forward_av, 0, 0, 1, 1)
            messagecontainer.attach(message_data_container, 1, 0, 1, 1)


        else:
            messagecontainer = Gtk.Label()
            css = '''#message_font_size {
            font-size: 12px;}'''
            gtkgui_helpers.add_css_to_widget(messagecontainer, css)
            messagecontainer.set_name('message_font_size')
            messagecontainer.set_text(message)
            messagecontainer.set_line_wrap(True)
            messagecontainer.set_justify(Gtk.Justification.LEFT)
            messagecontainer.set_halign(Gtk.Align.START)
        # TODO fix trouble with text padding )
        if not SAME_FROM:
            show2.pack_start(name_badge_role, True, True, 0)
        show2.pack_start(messagecontainer, True, True, 0)

        # SHOW3
        timestamp_label = Gtk.Label()
        timestamp_label.set_markup('<span font_desc=\'12px\' color=\'#666\'>14:44:42</span>')
        css = '''#xtimestamp {
        margin: 0px 16px;}'''
        gtkgui_helpers.add_css_to_widget(timestamp_label, css)
        timestamp_label.set_name('xtimestamp')
        show3.add(timestamp_label)


        show.set_size_request(64, -1)
        show3.set_size_request(95, -1)

        event_box = Gtk.EventBox()
        # event_box.add(simplegrid)
        # wids = [show, show2, show3]
        # event_box.connect('button-press-event', self.on_avatar_press_event, forward)

        self.box.pack_start(simplegrid, True, True, 0)
        simplegrid.show_all()



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
        self.textview.plugin_modified = True
        lineindex = buffer_.get_line_count() - 1
        prevline = buffer_.get_iter_at_line(lineindex)
        buffer_.delete(prevline, iter_)



        if IS_MSG:
            self.print_message(iter_, SAME_FROM, buffer_, nickname, message, role, badge, additional_data)
        #else:
            #self.print_server_info(iter_, buffer_, real_text)

        # TODO fix cyrillic



    def on_avatar_press_event(self, eb, event, additional_data):
        isme = False
        try: h = additional_data['nickname']
        except: isme = True

        def on_ok():
            return

        def on_cancel():
            return

        # left click
        if event.type == Gdk.EventType.BUTTON_PRESS and event.button == 1:
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

        # right klick
        elif event.type == Gdk.EventType.BUTTON_PRESS and event.button == 3:
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
