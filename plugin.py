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
import datetime

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
        self.description = _('Adds support Xabber Groups.')
        self.config_dialog = None
        self.controls = {}
        self.userdata = {}
        self.history_window_control = None

        self.events_handlers = {
            'decrypted-message-received': (ged.OUT_POSTGUI1, self._nec_decrypted_message_received),
            'raw-iq-received': (ged.OUT_PRECORE, self._nec_iq_received),
            'message-outgoing': (ged.OUT_POSTGUI1, self._nec_message_outgoing)
        }
        self.gui_extension_points = {
            'chat_control_base': (self.connect_with_chat_control,
                                       self.disconnect_from_chat_control),
            'print_real_text': (self.print_real_text, None),
            'roster_draw_contact': (self.connect_with_roster_draw_contact, None),
        }

    @log_calls('XabberGroupsPlugin')
    def activate(self):
        self.active = None
        roster = app.interface.roster
        col = Gtk.TreeViewColumn()
        roster.nb_ext_renderers += 1
        self.renderer_num = 11 + roster.nb_ext_renderers
        self.renderer = Gtk.CellRendererPixbuf()
        client_icon_rend = (
            'xgc_icon', self.renderer, False,
            'pixbuf', self.renderer_num,
            roster._fill_pep_pixbuf_renderer, self.renderer_num)
        # remove old column
        roster.tree.remove_column(roster.tree.get_column(0))
        # add new renderer in renderers list
        position = 'avatar'
        for renderer in roster.renderers_list:
            if renderer[0] == position:
                break
        num = roster.renderers_list.index(renderer)
        roster.renderers_list.insert(num, client_icon_rend)
        # fill and append column
        roster.fill_column(col)
        roster.tree.insert_column(col, 0)
        # redraw roster
        roster.columns += [GdkPixbuf.Pixbuf]
        self.active = True
        roster.setup_and_draw_roster()


    @log_calls('ClientsIconsPlugin')
    def connect_with_roster_draw_contact(self, roster, jid, account, contact):
        # TODO add update icon when add contact to allowjids
        print(roster)
        print(type(roster))
        print(roster.model)
        print(type(roster.model))
        print(jid)
        if jid in allowjids:
            child_iters = roster._get_contact_iter(jid, account, contact, roster.model)
            if not child_iters:
                return
            for iter_ in child_iters:
                if roster.model[iter_][self.renderer_num] is None:
                    icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "gc_icon.png")
                    pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_size(icon_path, 16, 16)
                    roster.model[iter_][self.renderer_num] = pixbuf


    @log_calls('XabberGroupsPlugin')
    def _nec_message_outgoing(self, obj):
        to_jid = obj.jid
        from_jid = obj.account
        from_jid = app.get_jid_from_account(from_jid)
        print(to_jid)
        print(from_jid)
        if to_jid in allowjids:
            add_data = self.userdata[to_jid][from_jid]
            obj.additional_data.update({'jid': add_data['jid'],
                                        'nickname': add_data['nickname'],
                                        'id': add_data['id'],
                                        'av_id': add_data['av_id'],
                                        'badge': add_data['badge'],
                                        'role': '',
                                        'message': obj.message,
                                        'ts': datetime.datetime.now().isoformat()
                                        })
        account = None
        accounts = app.contacts.get_accounts()
        myjid = from_jid
        for acc in accounts:
            realjid = app.get_jid_from_account(acc)
            realjid = app.get_jid_without_resource(str(realjid))
            if myjid == realjid:
                account = acc
        for jid in self.controls[account]:
            if jid not in allowjids:
                continue
            self.controls[account][jid].print_real_text(obj)

    @log_calls('XabberGroupsPlugin')
    def send_ask_for_rights(self, chat_control, to_jid, id=''):
        print(to_jid)
        print(chat_control.contact.name)
        print(chat_control.contact)
        print(chat_control.contact.jid)
        stanza_send = nbxmpp.Iq(to=to_jid, typ='get')
        stanza_send.setAttr('id', str(id))
        stanza_send.setTag('query').setNamespace('http://xabber.com/protocol/groupchat#members')
        stanza_send.getTag('query').setAttr('id', str(id))
        app.connections[chat_control.account].connection.send(stanza_send, now=True)


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
    def _nec_iq_received(self, obj):
        try:
            # check is iq from xabber gc
            item = obj.stanza.getTag('pubsub').getTag('items').getTag('item')
            base64avatar = item.getTag('data', namespace='urn:xmpp:avatar:data').getData()
            id = item.getAttr('id')
            avatar_loc = self.base64_to_image(base64avatar, id)
            print(avatar_loc)
        except:
            # check is iq = groupchat userdata from xabber gc
            item = obj.stanza.getTag('query', namespace=XABBER_GC+'#rights').getTag('item')
            id = item.getTag('id').getData()
            jid = item.getTag('jid').getData()
            badge = item.getTag('badge').getData()
            nickname = item.getTag('nickname').getData()
            av_id = item.getTag('metadata', namespace='urn:xmpp:avatar:metadata').getData()
            userdata = {'id': id,
                        'jid': jid,
                        'badge': badge,
                        'nickname': nickname,
                        'av_id': av_id}
            print('data\n'*10)
            room = obj.stanza.getAttr('from')
            myjid = obj.stanza.getAttr('to')
            myjid = app.get_jid_without_resource(str(myjid))
            print(room, myjid)
            self.userdata[room] = {}
            self.userdata[room][myjid] = userdata
            # self.controls[obj.account][room].remove_message_selection()
            # doesnt work

            account = None
            accounts = app.contacts.get_accounts()
            for acc in accounts:
                realjid = app.get_jid_from_account(acc)
                realjid = app.get_jid_without_resource(str(realjid))
                if myjid == realjid:
                    print(acc)
                    self.controls[acc][room].remove_message_selection()

        finally:
            return


    @log_calls('XabberGroupsPlugin')
    def _nec_decrypted_message_received(self, obj):
        '''
        get incoming messages, check it, do smth with them
        '''
        cr_invite = obj.stanza.getTag('invite', namespace=XABBER_GC)
        cr_message = obj.stanza.getTag('x', namespace=XABBER_GC)
        cr_right_query = obj.stanza.getTag('query', namespace=XABBER_GC+'#rights')
        if cr_invite:
            self.invite_to_chatroom_recieved(obj)
        elif cr_message:
            self.xabber_message_recieved(obj)
        elif cr_right_query:
            self.rights_query_recieved(obj)

    @log_calls('XabberGroupsPlugin')
    def rights_query_recieved(self, obj):
        myjid = obj.stanza.getAttr('to')
        myjid = app.get_jid_without_resource(str(myjid))
        fromjid = obj.jid
        userid = obj.stanza.getTag('query', namespace=XABBER_GC+'#rights').getTag('item').getTag('id').getData()
        jid = obj.stanza.getTag('query', namespace=XABBER_GC+'#rights').getTag('item').getTag('jid').getData()
        badge = obj.stanza.getTag('query', namespace=XABBER_GC+'#rights').getTag('item').getTag('badge').getData()
        nickname = obj.stanza.getTag('query', namespace=XABBER_GC+'#rights').getTag('item').getTag('nickname').getData()
        av_id = ''
        try:
            av_id = obj.stanza.getTag('query', namespace=XABBER_GC+'#rights').getTag('metadata',
                                                                                      namespace='urn:xmpp:avatar:metadata')
            av_id = av_id.getTag('info').getAttr('id')
        except:
            av_id = 'unknown'
        rights = {'jid': jid,
                  'nickname': nickname,
                  'id': userid,
                  'av_id': av_id,
                  'badge': badge
            }



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
                        'badge': fbadge,
                        'ts': delay
            }

        obj.additional_data.update({'jid': jid,
                                    'nickname': name,
                                    'message': message,
                                    'id': userid,
                                    'av_id': id,
                                    'role': role,
                                    'badge': badge,
                                    'forward': forward_m,
                                    'ts': datetime.datetime.now().isoformat()
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
        #if jid in allowjids:  # ask for rights if xgc if open chat control
        if account not in self.controls and jid in allowjids:
            self.controls[account] = {}
        self.controls[account][jid] = Base(self, chat_control.conv_textview, chat_control)
        self.send_ask_for_rights(chat_control, jid)
        print(account)
        print(jid)
        print('connect\n'*50)

    @log_calls('XabberGroupsPlugin')
    def disconnect_from_chat_control(self, chat_control):
        account = chat_control.contact.account.name
        jid = chat_control.contact.jid
        self.controls[account][jid].deinit_handlers()
        del self.controls[account][jid]

    @log_calls('XabberGroupsPlugin')
    def connect_with_history(self, history_window):
        if self.history_window_control:
            self.history_window_control.deinit_handlers()
        self.history_window_control = Base(
            self, history_window.history_textview)

    @log_calls('XabberGroupsPlugin')
    def disconnect_from_history(self, history_window):
        if self.history_window_control:
            self.history_window_control.deinit_handlers()
        self.history_window_control = None

    @log_calls('XabberGroupsPlugin')
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

    def __init__(self, plugin, textview, chat_control=None):
        # recieve textview to work with

        cli_jid = app.get_jid_from_account(chat_control.contact.account.name)
        room_jid = chat_control.contact.jid

        self.plugin = plugin
        self.textview = textview
        self.handlers = {}
        self.default_avatar = os.path.join(os.path.dirname(os.path.abspath(__file__)), "default.jpg")
        # self.default_avatar = base64.encodestring(open(default_avatar, "rb").read())

        self.previous_message_from = None
        self.last_message_date = None
        self.current_message_id = -1
        self.chosen_messages_data = []

        self.box = Gtk.Box(False, 0, orientation=Gtk.Orientation.VERTICAL)
        #self.box.set_size_request(self.textview.tv.get_allocated_width(), self.textview.tv.get_allocated_height())
        self.scrolled = Gtk.ScrolledWindow()
        self.scrolled.add(self.box)

        self.textview.tv.connect_after('size-allocate', self.resize)

        self.textview.tv.add(self.scrolled)
        self.scrolled.size_allocate(self.textview.tv.get_allocation())

        if chat_control and room_jid in allowjids:
            self.create_buttons(chat_control)

    def resize(self, widget, r):
        self.scrolled.set_size_request(r.width, r.height)
        messages = [m for m in self.box.get_children()]
        for i in messages:
            try:
                j = i.get_children()
                j[2].set_size_request(r.width - (64+95), -1)
            except: pass

        print(self.actions_hbox.get_children())

    def do_resize(self, messagebox):
        w = self.textview.tv.get_allocated_width()
        messagebox.set_size_request(w, -1)
        messagebox.get_children()[2].set_size_request(w - (64+95), -1)

    def deinit_handlers(self):
        # remove all register handlers on wigets, created by self.xml
        # to prevent circular references among objects
        for i in list(self.handlers.keys()):
            if self.handlers[i].handler_is_connected(i):
                self.handlers[i].disconnect(i)
            del self.handlers[i]


    def print_message(self, SAME_FROM, nickname, message, role, badge, additional_data, timestamp):

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

        # SHOW1
        pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(file, 32, 32, False)
        image = Gtk.Image.new_from_pixbuf(pixbuf)
        css = '''#xavatar {
        margin: 12px 16px 0px 16px;}'''
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
            name_badge_role = Gtk.Grid()

            info_name = Gtk.Label(nickname)
            css = '''#info_name {
            color: #D32F2F;
            font-size: 12px;
            margin-right: 4px;
            margin-top: 10px;}'''
            gtkgui_helpers.add_css_to_widget(info_name, css)
            info_name.set_name('info_name')

            info_badge = Gtk.Label(badge)
            css = '''#info_badge {
            color: black;
            font-size: 10px;
            margin-right: 4px;
            margin-top: 10px;}'''
            gtkgui_helpers.add_css_to_widget(info_badge, css)
            info_badge.set_name('info_badge')

            info_role = Gtk.Label(role)
            css = '''#info_role {
            color: white;
            font-size: 10px;
            background-color: #CCC;
            border-radius: 3px;
            padding: 2px 3px 0px 3px;
            margin: 2px;
            margin-top: 10px;}'''
            gtkgui_helpers.add_css_to_widget(info_role, css)
            info_role.set_name('info_role')

            name_badge_role.attach(info_name, 0, 0, 1, 1)
            name_badge_role.attach(info_badge, 1, 0, 1, 1)
            name_badge_role.attach(info_role, 2, 0, 1, 1)

        if IS_FORWARD:
            pixbuf2 = GdkPixbuf.Pixbuf.new_from_file_at_scale(file2, 32, 32, False)
            image2 = Gtk.Image.new_from_pixbuf(pixbuf2)
            css = '''#xavatar-forward {
            margin-right: 8px;
            margin-top: 12px;}'''
            gtkgui_helpers.add_css_to_widget(image2, css)
            image2.set_name('xavatar-forward')

            avatar2_event_box = Gtk.EventBox()
            avatar2_event_box.connect('button-press-event', self.on_avatar_press_event, forward)
            avatar2_event_box.connect('enter-notify-event', self.on_enter_event)
            avatar2_event_box.connect('leave-notify-event', self.on_leave_event)
            avatar2_event_box.add(image2)


            show_forward_av = Gtk.Grid()
            show_forward_av.add(avatar2_event_box)

            name_badge_role2 = Gtk.Grid()

            info_name2 = Gtk.Label(forward['nickname'])
            css = '''#info_name {
            color: #D32F2F;
            font-size: 12px;
            margin-right: 4px;
            margin-top: 10px;}'''
            gtkgui_helpers.add_css_to_widget(info_name2, css)
            info_name2.set_name('info_name')

            info_badge2 = Gtk.Label(forward['badge'])
            css = '''#info_badge {
            color: black;
            font-size: 10px;
            margin-right: 4px;
            margin-top: 10px;}'''
            gtkgui_helpers.add_css_to_widget(info_badge2, css)
            info_badge2.set_name('info_badge')

            info_role2 = Gtk.Label(forward['role'])
            css = '''#info_role {
            color: white;
            font-size: 10px;
            background-color: #CCC;
            border-radius: 3px;
            padding: 2px 3px 0px 3px;
            margin: 2px;
            margin-top: 10px;}'''
            gtkgui_helpers.add_css_to_widget(info_role2, css)
            info_role2.set_name('info_role')

            try:
                info_ts = str(forward['ts'])
                dttoday = datetime.date.today()
                dttoday = str(dttoday)[2:10]
                dtdate = info_ts.split('T')[0]
                dtdate = str(dtdate)[2:10]
                dtd = datetime.datetime.strptime(dtdate, "%y-%m-%d")
                dtd = dtd.strftime("%b %d")
                dttime = info_ts.split('T')[1]
                dttime = dttime[:8]
                if dttoday == dtdate:
                    info_ts = dttime
                else:
                    info_ts = dtd
            except:
                info_ts = '???'

            info_timestamp = Gtk.Label(info_ts)
            css = '''#info_ts {
            margin-top: 10px;
            font-size: 12px;
            color: #666;}'''
            gtkgui_helpers.add_css_to_widget(info_timestamp, css)
            info_timestamp.set_name('info_ts')

            name_badge_role2.attach(info_name2, 0, 0, 1, 1)
            name_badge_role2.attach(info_badge2, 1, 0, 1, 1)
            name_badge_role2.attach(info_role2, 2, 0, 1, 1)
            name_badge_role2.attach(info_timestamp, 3, 0, 1, 1)

            messagetext = Gtk.Label()
            css = '''#message_font_size {
            font-size: 12px;
            margin-top: 6px;
            margin-bottom: 8px;}'''
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
            font-size: 12px;
            margin-top: 6px;
            margin-bottom: 8px;}'''
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
        timestamp_label = Gtk.Label(timestamp)
        css = '''#xtimestamp {
        margin: 0px 16px;
        margin-top: 10px;
        font-size: 12px;
        color: #666;}'''
        gtkgui_helpers.add_css_to_widget(timestamp_label, css)
        timestamp_label.set_name('xtimestamp')
        show3.add(timestamp_label)


        show.set_size_request(64, -1)
        show3.set_size_request(95, -1)

        Message_eventBox = Gtk.EventBox()
        simplegrid.attach(Message_eventBox, 0, 0, 3, 1)
        self.current_message_id += 1
        Message_eventBox.connect('button-press-event', self.on_message_click, additional_data,
                                 self.current_message_id, simplegrid, timestamp, nickname, message)
        Message_eventBox.connect('enter-notify-event', self.on_enter_event)
        Message_eventBox.connect('leave-notify-event', self.on_leave_event)

        self.box.pack_start(simplegrid, False, False, 0)
        # set size of message by parent width after creating
        self.do_resize(simplegrid)
        simplegrid.show_all()

    def print_server_info(self, real_text):
        server_info = Gtk.Label(real_text)
        css = '''#server_info {
        padding: 8px 0px;
        font-size: 12px;
        color: #9E9E9E;
        font-style: italic;}'''
        gtkgui_helpers.add_css_to_widget(server_info, css)
        server_info.set_name('server_info')
        self.box.pack_start(server_info, False, False, 0)
        server_info.show_all()

    def print_real_text(self, real_text, text_tags, graphics, iter_, additional_data):

        nickname = None
        print(additional_data)
        print(graphics)
        print(type(graphics))

        try:
            timestamp = str(additional_data['ts'])
            dtdate = timestamp.split('T')[0]
            dtdate = str(dtdate)[2:10]
            dttime = timestamp.split('T')[1]
            dttime = dttime[:8]

            if dtdate != self.last_message_date:
                self.previous_message_from = None
                self.last_message_date = dtdate
                dt = datetime.datetime.strptime(dtdate, "%y-%m-%d")
                self.print_server_info(dt.strftime("%A, %d %B, %Y"))

            timestamp = dttime
        except: timestamp = '???'

        SAME_FROM = False
        try:
            nickname = additional_data['nickname']
            message = additional_data['message']
            role = additional_data['role']
            badge = additional_data['badge']
            if self.previous_message_from == additional_data['id']:
                SAME_FROM = True
            self.previous_message_from = additional_data['id']
            IS_MSG = True
        except:
            IS_MSG = False
            self.previous_message_from = None

        buffer_ = self.textview.tv.get_buffer()

        # delete old "[time] name: "
        # upd. and put [time] into message timestamp
        self.textview.plugin_modified = True
        start = buffer_.get_start_iter()
        end = buffer_.get_end_iter()
        buffer_.delete(start, end)




        if IS_MSG:
            self.print_message(SAME_FROM, nickname, message, role, badge, additional_data, timestamp)
        else:
            self.print_server_info(real_text)




    def on_avatar_press_event(self, eb, event, additional_data):
        def on_ok():
            return

        def on_cancel():
            return

        # left click
        if event.type == Gdk.EventType.BUTTON_PRESS and event.button == 1:
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
    # TODO fix events
    def on_enter_event(self, eb, event):
        print('enter')
        return

    # Change mouse pointer to default when mouse leaves the eventbox
    def on_leave_event(self, eb, event):
        print('leave')
        return


    def on_message_click(self, eb, event, data, id, widget, timestamp, nickname, message):

        # search message in chosen_messages_data by id
        for message_data in self.chosen_messages_data:
            if message_data[0] == id:
                print('deactivate')
                self.chosen_messages_data.remove(message_data)
                print(self.chosen_messages_data)
                css = '''#messagegrid {
                background-color: #FFFFFF;}'''
                gtkgui_helpers.add_css_to_widget(widget, css)
                widget.set_name('messagegrid')
                if len(self.chosen_messages_data) == 0:
                    self.show_othr_hide_xbtn()
                else:
                    self.show_xbtn_hide_othr()
                return

        print('activate')
        new_message_data = [id, data, timestamp, nickname, message]
        self.chosen_messages_data.append(new_message_data)
        print(self.chosen_messages_data)
        css = '''#messagegrid {
        background-color: #FFCCCC;}'''
        gtkgui_helpers.add_css_to_widget(widget, css)
        widget.set_name('messagegrid')
        self.button_copy.show()
        self.button_forward.show()
        self.button_reply.show()
        if len(self.chosen_messages_data) == 0:
            self.show_othr_hide_xbtn()
        else:
            self.show_xbtn_hide_othr()

    def create_buttons(self, chat_control):
        self.actions_hbox = chat_control.xml.get_object('hbox')

        #childs = self.actions_hbox.get_children()


        css = '''#Xbutton {
        margin: 0 5px;
        padding: 0 10px;
        color: #FFFFFF;
        background-color: #D32F2F;
        background: #D32F2F;
        border-radius: 2px;
        box-shadow: 0 2px 5px 0 rgba(0, 0, 0, 0.16), 0 2px 10px 0 rgba(0, 0, 0, 0.12);
        font-size: 12px;
        font-weight: bold;
        }
        #XCbutton {
        margin: 0 5px;
        padding: 0 10px;
        color: #D32F2F;
        background-color: #FFFFFF;
        background: #FFFFFF;
        border-radius: 2px;
        font-size: 12px;
        font-weight: bold;
        }
        #XCbutton:hover{
        background-color: #E0E0E0;
        background: #E0E0E0;
        }
        '''


        # buttons configs
        self.button_copy = Gtk.Button(label='COPY', stock=None, use_underline=False)
        self.button_copy.set_tooltip_text(_('copy text from messages widgets (press ctrl+v to paste it)'))
        id_ = self.button_copy.connect('clicked', self.on_copytext_clicked)
        chat_control.handlers[id_] = self.button_copy
        gtkgui_helpers.add_css_to_widget(self.button_copy, css)
        self.button_copy.set_name('Xbutton')

        self.button_forward = Gtk.Button(label='FORWARD', stock=None, use_underline=False)
        self.button_forward.set_tooltip_text(_('resend printed messages for someone'))
        id_ = self.button_forward.connect('clicked', self.on_forward_clicked)
        chat_control.handlers[id_] = self.button_forward
        gtkgui_helpers.add_css_to_widget(self.button_forward, css)
        self.button_forward.set_name('Xbutton')

        self.button_reply = Gtk.Button(label='REPLY', stock=None, use_underline=False)
        self.button_reply.set_tooltip_text(_('resend printed messages for this user'))
        id_ = self.button_reply.connect('clicked', self.on_reply_clicked)
        chat_control.handlers[id_] = self.button_reply
        gtkgui_helpers.add_css_to_widget(self.button_reply, css)
        self.button_reply.set_name('Xbutton')

        self.button_cancel = Gtk.Button(label='CANCEL', stock=None, use_underline=False)
        self.button_cancel.set_tooltip_text(_('clear selection'))
        id_ = self.button_cancel.connect('clicked', self.remove_message_selection)
        chat_control.handlers[id_] = self.button_cancel
        gtkgui_helpers.add_css_to_widget(self.button_cancel, css)
        self.button_cancel.set_name('XCbutton')

        self.button_copy.get_style_context().add_class('chatcontrol-actionbar-button')
        self.button_forward.get_style_context().add_class('chatcontrol-actionbar-button')
        self.button_reply.get_style_context().add_class('chatcontrol-actionbar-button')
        self.button_cancel.get_style_context().add_class('chatcontrol-actionbar-button')

        self.buttongrid = Gtk.Grid()
        self.buttongrid.attach(self.button_forward, 0, 0, 1, 1)
        self.buttongrid.attach(self.button_reply, 1, 0, 1, 1)
        self.buttongrid.attach(self.button_copy, 2, 0, 1, 1)
        self.buttongrid.attach(self.button_cancel, 4, 0, 1, 1)
        self.actions_hbox.add(self.buttongrid)
        self.buttongrid.show()
        self.actions_hbox.pack_start(self.buttongrid, True, True, 0)
        self.actions_hbox.reorder_child(self.buttongrid, 0)

        self.actions_hbox.connect_after('size-allocate', self.resize_actions)
        self.button_copy.set_size_request(95, 35)
        self.button_forward.set_size_request(95, 35)
        self.button_reply.set_size_request(95, 35)
        self.button_cancel.set_size_request(95, 35)

        #self.actions_hbox.pack_start(self.button_copy, False, False, 0)
        #self.actions_hbox.pack_start(self.button_forward, False, False, 0)
        #self.actions_hbox.pack_start(self.button_reply, False, False, 0)

        #self.actions_hbox.reorder_child(self.button_copy, len(self.actions_hbox.get_children()) - 4)
        #self.actions_hbox.reorder_child(self.button_forward, len(self.actions_hbox.get_children()) - 3)
        #self.actions_hbox.reorder_child(self.button_reply, len(self.actions_hbox.get_children()) - 2)

        # info about acts which was visible before tap message
        self.was_wisible_acts = []
        self.show_othr_hide_xbtn()

    def resize_actions(self, widget, r):
        self.button_cancel.set_property("margin-left", r.width - 420)

    def remove_message_selection(self, w=None):
        print('remove_message_selection')
        self.chosen_messages_data = []
        self.show_othr_hide_xbtn()
        messages = [m for m in self.box.get_children()]
        for widget in messages:
            css = '''#messagegrid {
            background-color: #FFFFFF;}'''
            gtkgui_helpers.add_css_to_widget(widget, css)

    def show_xbtn_hide_othr(self):
        actions = [m for m in self.actions_hbox.get_children()]
        for act in actions:
            if act.get_visible():
                self.was_wisible_acts.append(act)
            act.set_visible(False)
        self.buttongrid.show()

    def show_othr_hide_xbtn(self):
        for act in self.was_wisible_acts:
            act.set_visible(True)
        self.buttongrid.hide()


    def on_copytext_clicked(self, widget):
        copied_text = ''
        date = None
        for data in self.chosen_messages_data:
            dtdate = data[1]['ts'].split('T')[0]
            dtdate = str(dtdate)[2:10]
            if dtdate != date:
                date = dtdate
                dt = datetime.datetime.strptime(dtdate, "%y-%m-%d")
                dt = dt.strftime("%A, %d %B, %Y")
                copied_text += dt + '\n'
            try:
                copied_text += '[' + data[2] + '] ' + data[3] + ':\n' + data[4] + '\n'
                # TODO add name, badge etc. to 'me' messages
            finally:
                copied_text += ''
        clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
        clipboard.set_text(copied_text, -1)
        self.remove_message_selection()

    def on_forward_clicked(self, widget):
        print('forward clicked!')

    def on_reply_clicked(self, widget):
        print('reply clicked!')
