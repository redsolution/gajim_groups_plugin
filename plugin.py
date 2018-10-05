# -*- coding: utf-8 -*-
import logging
import uuid
import nbxmpp
import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gdk, GLib, GdkPixbuf, Pango, Gio
from groups_plugin.plugin_dialogs import UserDataDialog, CreateGroupchatDialog, InviteMemberDialog, ChatEditDialog
from nbxmpp import simplexml
from nbxmpp.protocol import JID
from gajim import dialogs
from gajim import gtkgui_helpers
from gajim.common import ged
from gajim.common import app
from gajim.common import configpaths
from gajim.common import connection
from gajim.plugins import GajimPlugin
from gajim.plugins.helpers import log_calls
import base64
import os
import datetime
import hashlib

# namespaces & logger
log = logging.getLogger('gajim.plugin_system.XabberGroupsPlugin')
XABBER_GC = 'http://xabber.com/protocol/groupchat'
XABBER_GC_invite = 'http://xabber.com/protocol/groupchat#invite'

AVATARS_DIR = os.path.join(configpaths.get('MY_CACHE'), 'xabavatars')
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

def get_account_from_jid(jid):
    jid = app.get_jid_without_resource(str(jid))
    account = None
    accounts = app.contacts.get_accounts()
    for acc in accounts:
        realjid = app.get_jid_from_account(acc)
        realjid = app.get_jid_without_resource(str(realjid))
        if jid == realjid:
            account = acc
    return account

class XabberGroupsPlugin(GajimPlugin):

    @log_calls('XabberGroupsPlugin')
    def init(self):
        self.description = _('Adds support Xabber Groups.')
        self.config_dialog = None
        self.controls = {}
        self.userdata = {}
        self.room_data = {}
        self.chat_edit_dialog_windows = {}
        self.nonupdated_stanza_id_messages = {}

        self.events_handlers = {
            'decrypted-message-received': (ged.OUT_POSTGUI1, self._nec_decrypted_message_received),
            'raw-message-received': (ged.OUT_POSTGUI1, self._raw_message_received),
            'raw-iq-received': (ged.OUT_PRECORE, self._nec_iq_received),
            'stanza-message-outgoing': (ged.OUT_POSTGUI1, self._nec_message_outgoing),
            'presence-received': (ged.POSTGUI, self.presence_received)
        }
        self.gui_extension_points = {
            'chat_control_base': (self.connect_with_chat_control,
                                       self.disconnect_from_chat_control),
            'print_real_text': (self.print_real_text, None),
            'roster_draw_contact': (self.connect_with_roster_draw_contact, None),
        }

    @log_calls('XabberGroupsPlugin')
    def activate(self):
        create_groupcaht_name = _('Add group chat')
        menubar = app.app.get_menubar()
        menubar.append(create_groupcaht_name, "app.create-xabber-groupchat")
        new_action = Gio.SimpleAction.new("create-xabber-groupchat", None)
        new_action.connect("activate", self.start_CreateGroupchatDialog)
        app.app.add_action(new_action)

        # gajim clear menu and next build its own

    def start_CreateGroupchatDialog(self, action, parameter):
        dialog = CreateGroupchatDialog(self)
        response = dialog.popup()

    @log_calls('ClientsIconsPlugin')
    def presence_received(self, obj):
        roster = app.interface.roster
        contact = app.contacts.get_contact_with_highest_priority(obj.conn.name, obj.jid)
        iters = roster._get_contact_iter(obj.jid, obj.conn.name, contact, roster.model)
        iter_ = iters[0]
        is_group = obj.stanza.getTag('x', namespace=XABBER_GC)
        if is_group:
            # set icon in roster, add jid to group list
            addallowjid(obj.jid)
            icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "gc_icon.png")
            pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_size(icon_path, 16, 16)
            image = Gtk.Image()
            image.show()
            image.set_from_pixbuf(pixbuf)
            roster.model[iter_][0] = image

            # send ask for user rights
            room = is_group.getTag('jid').getData()
            myjid = app.get_jid_without_resource(str(obj.stanza.getAttr('to')))

            self.send_ask_for_rights(myjid, room, type='XGCUserdata')

            # get room data
            name = is_group.getTag('name').getData()
            anonymous = is_group.getTag('anonymous').getData()
            searchable = is_group.getTag('searchable').getData()
            model = is_group.getTag('model').getData()
            description = is_group.getTag('description').getData()
            pinned_message = is_group.getTag('pinned-message').getData()

            old_pin = None
            if room in self.room_data:
                old_pin = self.room_data[room]['pinned']

            # update room data
            room_data = {'name': name,
                         'anonymous': anonymous,
                         'searchable': searchable,
                         'model': model,
                         'description': description,
                         'pinned': pinned_message}
            if room not in self.room_data:
                self.room_data[room] = {}
            self.room_data[room] = room_data

            # if pinned send ask for pinned
            if pinned_message:
                self.send_ask_for_pinned_message(myjid, room, pinned_message)

            # if pinned is empty, clear pinned
            else:
                acc = get_account_from_jid(myjid)
                if acc in self.controls:
                    if room in self.controls[acc]:
                        self.controls[acc][room].set_unpin_message()



        '''
            <presence to="maksim.batyatin@redsolution.com/gajim.42SK1ULX" from="redsolution@xmppdev01.xabber.com/Groupchat">
               <x xmlns="http://xabber.com/protocol/groupchat">
                  <jid>redsolution@xmppdev01.xabber.com</jid>
                  <name>redsolution</name>
                  <anonymous>false</anonymous>
                  <searchable>true</searchable>
                  <model>open</model>
                  <description>Group Chat</description>
                  <pinned-message>1537273099998861</pinned-message>
                  <contacts />
                  <domains />
               </x>
               <collect xmlns="http://xabber.com/protocol/groupchat">yes</collect>
            </presence>
        '''

    @log_calls('ClientsIconsPlugin')
    def connect_with_roster_draw_contact(self, roster, jid, account, contact):
        if jid in allowjids:
            child_iters = roster._get_contact_iter(jid, account, contact, roster.model)
            if not child_iters:
                return
            for iter_ in child_iters:
                icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "gc_icon.png")
                pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_size(icon_path, 16, 16)
                image = Gtk.Image.new_from_pixbuf(pixbuf)
                roster.model[iter_][0] = image

    @log_calls('XabberGroupsPlugin')
    def _nec_message_outgoing(self, obj):
        to_jid = obj.jid
        from_jid = obj.account
        from_jid = app.get_jid_from_account(from_jid)
        if to_jid in allowjids:
            add_data = self.userdata[to_jid][from_jid]
            obj.additional_data.update({'jid': add_data['jid'],
                                        'nickname': add_data['nickname'],
                                        'id': add_data['id'],
                                        'av_id': add_data['av_id'],
                                        'badge': add_data['badge'],
                                        'role': add_data['role'],
                                        'message': obj.message,
                                        'ts': datetime.datetime.now().isoformat(),
                                        'stanza_id': obj.stanza_id,
                                        'forward': None
                                        })
            self.nonupdated_stanza_id_messages[obj.stanza_id] = obj

    @log_calls('XabberGroupsPlugin')
    def send_ask_history_when_connect(self, room, myjid):
        print(room)
        print(myjid)
        stanza_send = nbxmpp.Iq(to=room, typ='set')
        stanza_send.setTag('query', namespace='urn:xmpp:mam:2').setAttr('queryid', 'XMAMessage')
        q = stanza_send.getTag('query').setTag('set', namespace='http://jabber.org/protocol/rsm')
        q.setTag('max').setData('40')
        q.setTag('before')
        account = get_account_from_jid(myjid)
        app.connections[account].connection.send(stanza_send, now=True)
        '''
        <iq type='set' id='juliet1'>
             <query xmlns="urn:xmpp:mam:1" queryid="2865943C-2B10-44D8-894C-E5EE646DE1CF">
                  <set xmlns="http://jabber.org/protocol/rsm">
                     <max>40</max>
                     <before />
                  </set>
               </query>
        </iq>
        '''

    @log_calls('XabberGroupsPlugin')
    def send_ask_for_hisrory_when_top_reached(self, room, myjid, stanza_id):
        print(room)
        print(myjid)
        stanza_send = nbxmpp.Iq(to=room, typ='set')
        stanza_send.setTag('query', namespace='urn:xmpp:mam:2').setAttr('queryid', 'XMAMessage')
        q = stanza_send.getTag('query').setTag('set', namespace='http://jabber.org/protocol/rsm')
        q.setTag('max').setData('40')
        q.setTag('before').setData(stanza_id)
        account = get_account_from_jid(myjid)
        app.connections[account].connection.send(stanza_send, now=True)

    @log_calls('XabberGroupsPlugin')
    def send_set_pinned_message(self, room, myjid, stanza_id):
        '''
        <iq from='juliet@capulet.it/balcony' to='mychat@capulet.it' type='set' id='3'>
          <update xmlns='http://xabber.com/protocol/groupchat'>
            <pinned-message>5f3dbc5e-e1d3-4077-a492-693f3769c7ad</pinned-message>
          </update>
        </iq>
        '''
        print(room)
        print(myjid)
        print(stanza_id)
        stanza_send = nbxmpp.Iq(to=room, typ='set')
        stanza_send.setTag('update').setNamespace(XABBER_GC)
        stanza_send.getTag('update').setTag('pinned-message').setData(stanza_id)
        account = get_account_from_jid(myjid)
        app.connections[account].connection.send(stanza_send, now=True)

    @log_calls('XabberGroupsPlugin')
    def send_invite_to_chatroom(self, chat_jid, from_jid, invite_jid, invite_by_chat, send_my_data, reason):
        if invite_by_chat:
            stanza_send = nbxmpp.Iq(to=chat_jid, typ='set', frm=from_jid)
            stanza_send.setTag('invite').setNamespace('http://xabber.com/protocol/groupchat#invite')
            stanza_send.getTag('invite').setTag('jid').setData(invite_jid)
            if send_my_data:
                stanza_send.getTag('invite').setTag('send').setData('true')
            stanza_send.getTag('invite').setTag('reason').setData(reason)
            account = get_account_from_jid(from_jid)
            app.connections[account].connection.send(stanza_send, now=True)

        else:
            join_text = _('To join a group chat, add ' + chat_jid + ' to your contact list.')
            stanza_send = nbxmpp.Message(to=invite_jid, typ='chat', frm=from_jid)
            stanza_send.setTag('invite').setNamespace('http://xabber.com/protocol/groupchat#invite')
            stanza_send.getTag('invite').setAttr('jid', chat_jid)
            stanza_send.getTag('invite').setTag('reason').setData(reason)
            stanza_send.setTag('body').setData(join_text)
            account = get_account_from_jid(from_jid)
            app.connections[account].connection.send(stanza_send, now=True)

    @log_calls('XabberGroupsPlugin')
    def send_publish_avatar_data(self, avatar_data, hash, to_jid, from_jid, u_id = None):
        if not u_id:
            u_id = self.userdata[to_jid][from_jid]['id']
        account = get_account_from_jid(from_jid)
        stanza_send = nbxmpp.Iq(to=to_jid, typ='set', frm=from_jid)
        stanza_send.setAttr('id', 'xgcPublish1')
        stanza_send.setTag('pubsub').setNamespace('http://jabber.org/protocol/pubsub')
        stanza_send.getTag('pubsub').setTagAttr('publish', 'node', 'urn:xmpp:avatar:data#'+u_id)
        stanza_send.getTag('pubsub').getTag('publish').setTagAttr('item', 'id', hash)
        stanza_send.getTag('pubsub').getTag('publish').getTag('item').setTag('data').setNamespace('urn:xmpp:avatar:data')
        stanza_send.getTag('pubsub').getTag('publish').getTag('item').getTag('data').setData(avatar_data)
        app.connections[account].connection.send(stanza_send, now=True)

    @log_calls('XabberGroupsPlugin')
    def send_ask_for_create_group_chat(self, myjid, data):
        server_domain = 'xmppdev01.xabber.com'
        stanza_send = nbxmpp.Iq(to=server_domain, typ='set')
        stanza_send.setAttr('id', 'CreateXGroupChat1')
        stanza_send.setTag('create').setNamespace(XABBER_GC)
        if data['jid']:
            stanza_send.getTag('create').setTag('localpart').setData(data['jid'])
        stanza_send.getTag('create').setTag('name').setData(data['name'])
        stanza_send.getTag('create').setTag('anonymous').setData(data['is_anon'])
        stanza_send.getTag('create').setTag('searchable').setData(data['is_search'])
        stanza_send.getTag('create').setTag('discoverable').setData(data['is_discov'])
        stanza_send.getTag('create').setTag('description').setData(data['desc'])
        stanza_send.getTag('create').setTag('access').setData(data['access'])
        # TODO <domains>
        stanza_send.getTag('create').setTag('collect-avatar').setData(data['is_collect'])
        account = get_account_from_jid(myjid)
        app.connections[account].connection.send(stanza_send, now=True)

    @log_calls('XabberGroupsPlugin')
    def send_unblock_or_revoke(self, myjid, room, jid_id, unblock=False, revoke=False):
        acc = get_account_from_jid(myjid)
        print(acc)
        if unblock:
            stanza_send = nbxmpp.Iq(to=room, typ='set')
            stanza_send.setID('XGCBlockUser')
            unblock = stanza_send.setTag('unblock', namespace='http://xabber.com/protocol/groupchat#block')
            unblock.setTag('id').setData(jid_id)
            app.connections[acc].connection.send(stanza_send, now=True)

        if revoke:
            stanza_send = nbxmpp.Iq(to=room, typ='set')
            stanza_send.setID('XGCRevokeUser')
            revoke = stanza_send.setTag('revoke', namespace='http://xabber.com/protocol/groupchat#invite')
            revoke.setTag('jid').setData(jid_id)
            app.connections[acc].connection.send(stanza_send, now=True)

    @log_calls('XabberGroupsPlugin')
    def send_ask_for_blocks_invites(self, myjid, room, type=''):
        acc = get_account_from_jid(myjid)
        print(acc)
        stanza_send = nbxmpp.Iq(to=room, typ='get')
        stanza_send.setAttr('id', type)
        if type == 'GCBlockedList':
            stanza_send.setTag('query').setNamespace('http://xabber.com/protocol/groupchat#block')
        elif type == 'GCInvitedList':
            stanza_send.setTag('query').setNamespace('http://xabber.com/protocol/groupchat#invite')
        app.connections[acc].connection.send(stanza_send, now=True)

    @log_calls('XabberGroupsPlugin')
    def send_ask_for_rights(self, myjid, room, id='', type='', mydata=True):
        acc = get_account_from_jid(myjid)
        print(acc)
        stanza_send = nbxmpp.Iq(to=room, typ='get')
        stanza_send.setAttr('id', type)
        stanza_send.setTag('query').setNamespace('http://xabber.com/protocol/groupchat#members')
        if mydata:
            stanza_send.getTag('query').setAttr('id', str(id))
        app.connections[acc].connection.send(stanza_send, now=True)

    @log_calls('XabberGroupsPlugin')
    def send_set_user_name(self, myjid, room, user_id, new_name):
        stanza_send = nbxmpp.Iq(to=room, typ='set')
        stanza_send.setTag('query').setNamespace('http://xabber.com/protocol/groupchat#members')
        stanza_send.getTag('query').setAttr('id', str(user_id))
        stanza_send.getTag('query').setTag('nickname').setData(new_name)
        acc = get_account_from_jid(myjid)
        app.connections[acc].connection.send(stanza_send, now=True)

    @log_calls('XabberGroupsPlugin')
    def send_set_user_badge(self, myjid, room, user_id, new_badge):
        stanza_send = nbxmpp.Iq(to=room, typ='set')
        stanza_send.setTag('query').setNamespace('http://xabber.com/protocol/groupchat#members')
        stanza_send.getTag('query').setAttr('id', str(user_id))
        stanza_send.getTag('query').setTag('badge').setData(new_badge)
        acc = get_account_from_jid(myjid)
        app.connections[acc].connection.send(stanza_send, now=True)

    @log_calls('XabberGroupsPlugin')
    def send_set_user_kick(self, myjid, room, user_id):
        stanza_send = nbxmpp.Iq(to=room, typ='set')
        stanza_send.setID('XGCKickUser')
        stanza_send.setTag('query').setNamespace('http://xabber.com/protocol/groupchat#members')
        stanza_send.getTag('query').setTagAttr('item', 'id', str(user_id))
        stanza_send.getTag('query').getTag('item').setAttr('role', 'none')
        acc = get_account_from_jid(myjid)
        app.connections[acc].connection.send(stanza_send, now=True)

    @log_calls('XabberGroupsPlugin')
    def send_set_user_block(self, myjid, room, user_id):
        stanza_send = nbxmpp.Iq(to=room, typ='set')
        stanza_send.setID('XGCBlockUser')
        block = stanza_send.setTag('block', namespace='http://xabber.com/protocol/groupchat#block')
        block.setTag('id').setData(user_id)
        acc = get_account_from_jid(myjid)
        app.connections[acc].connection.send(stanza_send, now=True)
        return

    @log_calls('XabberGroupsPlugin')
    def send_set_user_rights(self, myjid, room, user_id, rights):
        stanza_send = nbxmpp.Iq(to=room, typ='set')
        stanza_send.setTag('query').setNamespace('http://xabber.com/protocol/groupchat#members')
        stanza_send.getTag('query').setTagAttr('item', 'id', str(user_id))
        # item = stanza_send.getTag('query').getTag('item')
        # expires
        # 'never' for indefinitely
        # 'none' for remove

        for perm in rights['permissions']:
            item = stanza_send.getTag('query').getTag('item').addChild('permission')
            item.setAttr('name', perm)
            if rights['permissions'][perm]:
                item.setAttr('expires', 'never')
            else:
                item.setAttr('expires', 'none')

        for rest in rights['restrictions']:
            item = stanza_send.getTag('query').getTag('item').addChild('restriction')
            item.setAttr('name', rest)
            if rights['restrictions'][rest]:
                item.setAttr('expires', 'never')
            else:
                item.setAttr('expires', 'none')

        acc = get_account_from_jid(myjid)
        app.connections[acc].connection.send(stanza_send, now=True)

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
    def img_to_base64(self, filename):
        # encode image to base64, return base and hash
        # or return False if error
        try:
            with open(filename, "rb") as f:
                encoded_string = base64.b64encode(f.read())
                a = (encoded_string.decode("utf-8"))
                b = (hashlib.sha1(encoded_string).hexdigest())
                return a, b
        except:
            return False, filename

    @log_calls('XabberGroupsPlugin')
    def _nec_iq_received(self, obj):
        try: on_avatar_data_get = obj.stanza.getTag('pubsub').getTag('items').getTag('item').getTag('data',
                                                                                    namespace='urn:xmpp:avatar:data')
        except: on_avatar_data_get = False
        try: on_userdata_get = obj.stanza.getTag('query', namespace=XABBER_GC+'#rights').getTag('item')
        except: on_userdata_get = False
        try: on_messages_fin_get = (obj.stanza.getTag('fin', namespace='urn:xmpp:mam:2').getAttr('queryid') == 'XMAMessage')
        except: on_messages_fin_get = False
        on_uploading_avatar_response = (obj.stanza.getAttr('id') == 'xgcPublish1')
        on_publish_response = (obj.stanza.getAttr('id') == 'xgcPublish2')
        on_create_groupchat_response = (obj.stanza.getAttr('id') == 'CreateXGroupChat1')
        on_get_pinned_message = (obj.stanza.getAttr('id') == 'XGCPinnedMessage')
        on_get_chatmembers_data = (obj.stanza.getAttr('id') == 'GCMembersList')
        on_get_chat_blocked_data = (obj.stanza.getAttr('id') == 'GCBlockedList')
        on_get_chat_invited_data = (obj.stanza.getAttr('id') == 'GCInvitedList')

        if on_messages_fin_get:
            on_messages_fin_get = obj.stanza.getTag('fin', namespace='urn:xmpp:mam:2')
            myjid = obj.stanza.getAttr('to')
            acc = get_account_from_jid(myjid)
            room = obj.stanza.getAttr('from')
            top_message_id = on_messages_fin_get.getTag('set', namespace='http://jabber.org/protocol/rsm').getTag('first').getData()
            self.controls[acc][room].top_message_id = top_message_id
            self.controls[acc][room].is_waiting_for_messages = False
            self.controls[acc][room].xmam_loc_id = 0

        # XGCBlockUser
        # XGCKickUser
        # XGCRevokeUser
        on_block_user_chat_update = (obj.stanza.getAttr('id') == 'XGCBlockUser')
        on_revoke_user_chat_update = (obj.stanza.getAttr('id') == 'XGCRevokeUser')

        if on_block_user_chat_update:
            myjid = obj.stanza.getAttr('to')
            room = obj.stanza.getAttr('from')
            self.send_ask_for_blocks_invites(myjid, room, type='GCBlockedList')

        if on_revoke_user_chat_update:
            myjid = obj.stanza.getAttr('to')
            room = obj.stanza.getAttr('from')
            self.send_ask_for_blocks_invites(myjid, room, type='GCInvitedList')

        if on_get_chat_invited_data:
            print('invited data get\n'*10)
            room = obj.stanza.getAttr('from')
            room_dialog = self.chat_edit_dialog_windows[room]
            invited_users_data = []
            query = obj.stanza.getTag('query', namespace='http://xabber.com/protocol/groupchat#invite')
            users = query.getTags('user')
            for user in users:
                jid = user.getAttr('jid')
                print(user)
                print(jid)
                invited_users_data.append(jid)
            '''
            <error code='405' type='cancel'>
            <not-allowed xmlns='urn:ietf:params:xml:ns:xmpp-stanzas'/>
            <text xmlns='urn:ietf:params:xml:ns:xmpp-stanzas' xml:lang='en'>You have no permission to see list of invited users</text>
            </error>
            '''
            error = obj.stanza.getTag('error')
            if error:
                text = error.getTag('text', namespace='urn:ietf:params:xml:ns:xmpp-stanzas').getData()
                room_dialog.update_invited_list(error=text)
            else:
                room_dialog.update_invited_list(invited=invited_users_data)

        if on_get_chat_blocked_data:
            print('blocked data get\n'*10)
            room = obj.stanza.getAttr('from')
            room_dialog = self.chat_edit_dialog_windows[room]
            '''
            <query xmlns="http://xabber.com/protocol/groupchat#block">
                <user jid="devmuler@jabber.ru">xscgmq69xltyyjue</user>
            </query>
            '''
            blocked_users_data = []
            query = obj.stanza.getTag('query', namespace='http://xabber.com/protocol/groupchat#block')
            users = query.getTags('user')
            print(users)
            for user in users:
                id = user.getData()
                try: jid = user.getAttr('jid')
                except: jid = id
                print(user)
                print(jid)
                print(id)
                blocked_users_data.append({'jid': jid,
                                           'id': id})
            room_dialog.update_blocked_list(blocked_users_data)

        if on_get_chatmembers_data:
            print('on_get_chatmembers_data\n'*10)
            print(self.chat_edit_dialog_windows)
            room = obj.stanza.getAttr('from')
            room_dialog = self.chat_edit_dialog_windows[room]
            print(room)
            print(room_dialog)
            print(room_dialog.room)

            query = obj.stanza.getTag('query', namespace='http://xabber.com/protocol/groupchat#members')
            items = query.getTags('item')
            members_list = []
            for item in items:
                id = item.getTag('id').getData()
                try: jid = item.getTag('jid').getData()
                except: jid = id
                badge = item.getTag('badge').getData()
                nickname = item.getTag('nickname').getData()
                try:
                    av_id = item.getTag('metadata', namespace="urn:xmpp:avatar:metadata").getTag('info').getAttr('id')
                except: av_id = 'unknown'

                usertype = 'member'
                perms = item.getTags('permission')
                if len(perms) > 0:
                    usertype = 'admin'
                for p in perms:
                    print(p)
                    if p.getAttr('name') == 'owner':
                        usertype = 'owner'

                member = {
                    'id': id,
                    'jid': jid,
                    'badge': badge,
                    'nickname': nickname,
                    'av_id': av_id,
                    'usertype': usertype
                }

                members_list.append(member)

            room_dialog.update_members_list(members_list, AVATARS_DIR, )

        if on_get_pinned_message:
            count = obj.stanza.getTag('fin', namespace='urn:xmpp:mam:2').getTag('set', namespace='http://jabber.org/protocol/rsm').getTag('count').getData()
            room = obj.stanza.getAttr('from')
            myjid = obj.stanza.getAttr('to')
            if count == '0':
                account = get_account_from_jid(myjid)
                self.controls[account][room].set_unpin_message()

        if on_create_groupchat_response:
            iserror = obj.stanza.getTag('error')
            if not iserror:
                item = obj.stanza.getTag('created')
                jid = item.getTag('jid').getData()
                myjid = obj.stanza.getAttr('to')
                addallowjid(jid)
                account = get_account_from_jid(myjid)
                if account:
                    stanza_send = nbxmpp.Presence(to=jid, typ='subscribe', frm=myjid)
                    app.connections[account].connection.send(stanza_send, now=True)

        if on_avatar_data_get:
            # check is iq from xabber gc
            item = obj.stanza.getTag('pubsub').getTag('items').getTag('item')
            base64avatar = item.getTag('data', namespace='urn:xmpp:avatar:data').getData()
            id = item.getAttr('id')
            avatar_loc = self.base64_to_image(base64avatar, id)
            if obj.stanza.getAttr('id') == 'xgcUserAvData1':
                room = obj.stanza.getAttr('from')
                myjid = obj.stanza.getAttr('to')
                myjid = app.get_jid_without_resource(str(myjid))
                acc = get_account_from_jid(myjid)
                self.controls[acc][room].update_user_avatar(id)

        if on_userdata_get:
            if obj.stanza.getAttr('id') == 'XGCUserdata':
                # check is iq = groupchat userdata from xabber gc
                item = obj.stanza.getTag('query', namespace=XABBER_GC+'#rights').getTag('item')
                id = item.getTag('id').getData()
                jid = item.getTag('jid').getData()
                badge = item.getTag('badge').getData()
                nickname = item.getTag('nickname').getData()
                try:
                    av_id = item.getTag('metadata', namespace='urn:xmpp:avatar:metadata').getTag('info').getAttr('id')
                except: av_id = ''
                # rights
                i = item.getTags('restriction')
                restriction = {}
                for k in i:
                    restriction[k.getAttr('name')] = [k.getAttr('expires'),
                                                      k.getAttr('issued-by'),
                                                      k.getAttr('issued-at')]
                i = item.getTags('permission')
                permission = {}
                for k in i:
                    permission[k.getAttr('name')] = [k.getAttr('expires'),
                                                     k.getAttr('issued-by'),
                                                     k.getAttr('issued-at')]
                user_rights = {'restrictions': restriction,
                               'permissions': permission}

                role = ''
                if 'owner' in permission:
                    role = 'owner'
                elif len(permission) > 0:
                    role = 'admin'

                userdata = {'id': id,
                            'jid': jid,
                            'badge': badge,
                            'nickname': nickname,
                            'av_id': av_id,
                            'role': role,
                            'rights': user_rights}
                room = obj.stanza.getAttr('from')
                myjid = obj.stanza.getAttr('to')
                myjid = app.get_jid_without_resource(str(myjid))
                if room not in self.userdata:
                    self.userdata[room] = {}
                self.userdata[room][myjid] = userdata
                # self.controls[obj.account][room].remove_message_selection()
                # doesnt work

                acc = get_account_from_jid(myjid)
                self.controls[acc][room].on_userdata_updated(userdata)

            if obj.stanza.getAttr('id') == 'XGCUserOptions':
                room = obj.stanza.getAttr('from')
                myjid = app.get_jid_without_resource(str(obj.stanza.getAttr('to')))
                item = obj.stanza.getTag('query', namespace=XABBER_GC+'#rights').getTag('item')
                id = item.getTag('id').getData()
                try: jid = item.getTag('jid').getData()
                except: jid = 'Unknown'
                badge = item.getTag('badge').getData()
                nickname = item.getTag('nickname').getData()
                try:
                    av_id = item.getTag('metadata', namespace='urn:xmpp:avatar:metadata').getTag('info').getAttr('id')
                    avatar_loc = os.path.normpath(AVATARS_DIR + '/' + av_id + '.jpg')
                    try:
                        file = open(avatar_loc)
                    except:
                        av_id = ''
                        avatar_loc = os.path.join(os.path.dirname(os.path.abspath(__file__)), "default.png")
                        account = get_account_from_jid(myjid)
                        if account:
                            self.send_call_single_avatar(account, room, id, av_id)
                except:
                    av_id = ''
                    avatar_loc = os.path.join(os.path.dirname(os.path.abspath(__file__)), "default.png")
                pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(avatar_loc, 40, 40, False)
                image = Gtk.Image.new_from_pixbuf(pixbuf)
                # rights
                i = item.getTags('restriction')
                restriction = {}
                for k in i:
                    restriction[k.getAttr('name')] = [k.getAttr('expires'),
                                                      k.getAttr('issued-by'),
                                                      k.getAttr('issued-at')]
                i = item.getTags('permission')
                permission = {}
                for k in i:
                    permission[k.getAttr('name')] = [k.getAttr('expires'),
                                                     k.getAttr('issued-by'),
                                                     k.getAttr('issued-at')]
                user_rights = {'restrictions': restriction,
                               'permissions': permission}

                role = ''
                if 'owner' in permission:
                    role = 'owner'
                elif len(permission) > 0:
                    role = 'admin'

                userdata = {'id': id,
                            'jid': jid,
                            'badge': badge,
                            'nickname': nickname,
                            'av_id': av_id,
                            'role': role,
                            'rights': user_rights}

                acc = get_account_from_jid(myjid)
                if acc:
                    dialog = UserDataDialog(self, userdata, image, self.controls[acc][room])
                    response = dialog.popup()

        if on_uploading_avatar_response:
            # check is iq = response from xgc about uploading avatar
            item = obj.stanza.getTag('pubsub', namespace='http://jabber.org/protocol/pubsub')
            room = obj.stanza.getAttr('from')
            myjid = app.get_jid_without_resource(str(obj.stanza.getAttr('to')))
            u_id = item.getTag('publish').getAttr('node').split('#')[1]
            av_id = item.getTag('publish').getTag('item').getAttr('id')

            stanza_send = nbxmpp.Iq(to=room, frm=myjid, typ='set')
            stanza_send.setAttr('id', 'xgcPublish2')
            stanza_send.setTag('pubsub', namespace='http://jabber.org/protocol/pubsub')
            stanza_send.getTag('pubsub').setTagAttr('publish', 'node', 'urn:xmpp:avatar:metadata#' + u_id)
            stanza_send.getTag('pubsub').getTag('publish').setTagAttr('item', 'id', av_id)
            new_item = stanza_send.getTag('pubsub').getTag('publish').getTag('item')
            new_item.setTag('metadata', namespace='urn:xmpp:avatar:metadata')
            new_item.getTag('metadata').setTag('info')
            new_info = stanza_send.getTag('pubsub').getTag('publish').getTag('item').getTag('metadata').getTag('info')
            new_info.setAttr('bytes', '12345')
            new_info.setAttr('id', av_id)
            new_info.setAttr('height', '64')
            new_info.setAttr('width', '64')
            new_info.setAttr('type', 'image/jpeg')

            account = get_account_from_jid(myjid)
            app.connections[account].connection.send(stanza_send, now=True)

        if on_publish_response:
            item = obj.stanza.getTag('pubsub', namespace='http://jabber.org/protocol/pubsub')
            room = obj.stanza.getAttr('from')
            myjid = app.get_jid_without_resource(str(obj.stanza.getAttr('to')))
            u_id = item.getTag('publish').getAttr('node').split('#')[1]
            av_id = item.getTag('publish').getTag('item').getAttr('id')
            error = obj.stanza.getTag('error')
            if not error:
                self.userdata[room][myjid]['av_id'] = av_id
                acc = get_account_from_jid(myjid)
                # return dir or send stanza call for avatar and return False
                isexist = self.send_call_single_avatar(acc, room, u_id, av_id, 'xgcUserAvData1')
                if isexist:
                    self.controls[acc][room].update_user_avatar(av_id)

    @log_calls('XabberGroupsPlugin')
    def _nec_decrypted_message_received(self, obj):
        '''
        get incoming messages, check it, do smth with them
        '''
        cr_invite = obj.stanza.getTag('invite', namespace='http://xabber.com/protocol/groupchat#invite')
        cr_message = obj.stanza.getTag('x', namespace=XABBER_GC)
        if cr_invite:
            self.invite_to_chatroom_recieved(obj)
        elif cr_message:
            self.xabber_message_recieved(obj)

    @log_calls('XabberGroupsPlugin')
    def _raw_message_received(self, obj):
        '''
        <message to="maksim.batyatin@xmppdev01.xabber.com/gajim.H9QM8M4C" from="xmppdev01.xabber.com" type="headline">
           <received xmlns="http://xabber.com/protocol/unique">
              <time by="maksim.batyatin@xmppdev01.xabber.com" stamp="2018-09-27T06:27:30.218491Z" />
              <origin-id xmlns="urn:xmpp:sid:0" id="1ffc2541-699e-44b5-ba3c-f970ac8851f7" />
              <stanza-id xmlns="urn:xmpp:sid:0" by="maksim.batyatin@xmppdev01.xabber.com" id="1538029650218491" />
              <previous-id xmlns="http://xabber.com/protocol/previous" id="1538029617429984" />
           </received>
        </message>
        '''
        room = obj.stanza.getAttr('from')
        myjid = obj.stanza.getAttr('to')
        myjid = app.get_jid_without_resource(str(myjid))

        if obj.stanza.getAttr('type') == 'headline':
            received = obj.stanza.getTag('received', namespace='http://xabber.com/protocol/unique')
            if received.getTag('stanza-id').getAttr('by'):
                origin_id = received.getTag('origin-id').getAttr('id')
                stanza_id = received.getTag('stanza-id').getAttr('id')
                print(origin_id)
                print(stanza_id)
                self.nonupdated_stanza_id_messages[origin_id].additional_data['stanza_id'] = stanza_id
                # TODO upload additional data
                del self.nonupdated_stanza_id_messages[origin_id]
            return

        try:
            result = obj.stanza.getTag('result').getAttr('queryid') == None
            # forwarded
            message = obj.stanza.getTag('result').getTag('forwarded').getTag('message')
            timestamp = message.getTag('time').getAttr('stamp')
            nickname = message.getTag('x').getTag('nickname').getData()
            body = message.getTag('x').getTag('body').getData()
            account = get_account_from_jid(myjid)

            dtdate = timestamp.split('T')[0]
            dtdate = str(dtdate)[2:10]
            dt = datetime.datetime.strptime(dtdate, "%y-%m-%d")
            dtdate = dt.strftime("%d %B, %Y")
            dttime = timestamp.split('T')[1]
            dttime = dttime[:8]
            timestamp = dtdate + ' ' + dttime

            if result:
                self.controls[account][room].set_pin_message(nickname, timestamp, body)
        except: pass

        # forwarded
        if obj.stanza.getTag('result', namespace='urn:xmpp:mam:2').getAttr('queryid') == 'XMAMessage':
            room = obj.stanza.getAttr('from')
            myjid = obj.stanza.getAttr('to')
            account = get_account_from_jid(myjid)

            # <time xmlns='http://xabber.com/protocol/unique'
            # by='4test@xmppdev01.xabber.com'
            # stamp='2018-10-03T10:38:46.123295Z'/>

            message = obj.stanza.getTag('result', namespace='urn:xmpp:mam:2').getTag('forwarded', namespace='urn:xmpp:forward:0').getTag('message')
            name = message.getTag('x', namespace=XABBER_GC).getTag('nickname').getData()
            userid = message.getTag('x', namespace=XABBER_GC).getTag('id').getData()
            if not name:
                name = False
            message_text = message.getTag('x', namespace=XABBER_GC).getTag('body').getData()
            id = None
            try:
                id = message.getTag('x', namespace=XABBER_GC).getTag('metadata', namespace='urn:xmpp:avatar:metadata')
                id = id.getTag('info').getAttr('id')
            except: id = 'unknown'
            jid = None
            try:
                jid = message.getTag('x', namespace=XABBER_GC).getTag('jid').getData()
            except: jid = 'unknown'
            role = message.getTag('x', namespace=XABBER_GC).getTag('role').getData()
            badge = message.getTag('x', namespace=XABBER_GC).getTag('badge').getData()

            forwarded = message.getTag('origin-id', namespace='urn:xmpp:sid:0').getTag('forwarded', namespace='urn:xmpp:forward:0')

            forward_m = None
            if forwarded:
                print('forwarded\n' * 10)
                delay = forwarded.getTag('delay', namespace='urn:xmpp:delay').getAttr('stamp')
                fobj = forwarded.getTag('message')
                fstanza_id = fobj.getTag('stanza-id').getAttr('id')

                try:  fname = fobj.getTag('x', namespace=XABBER_GC).getTag('nickname').getData()
                except: fname = name
                try:  fuserid = fobj.getTag('x', namespace=XABBER_GC).getTag('id').getData()
                except:  fuserid = userid
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
                    if fuserid == userid: fid = id
                    else: fid = 'unknown'
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
                             'ts': delay,
                             'stanza_id': fstanza_id
                             }

            stanza_id = message.getTag('stanza-id').getAttr('id')
            timestamp = message.getTag('time').getAttr('stamp')
            additional_data = {'jid': jid,
                               'nickname': name,
                               'message': message_text,
                               'id': userid,
                               'av_id': id,
                               'role': role,
                               'badge': badge,
                               'forward': forward_m,
                               'stanza_id': stanza_id,
                               'ts': timestamp
                               }
            self.controls[account][room].print_real_text('', [], False, None, additional_data, mam_loc=True)


    @log_calls('XabberGroupsPlugin')
    def invite_to_chatroom_recieved(self, obj):
        myjid = obj.stanza.getAttr('to')
        myjid = app.get_jid_without_resource(str(myjid))
        jid = obj.stanza.getTag('invite').getAttr('jid')
        if not jid:
            jid = obj.stanza.getTag('invite').getTag('jid').getData()

        def on_ok():
            addallowjid(jid)
            account = get_account_from_jid(myjid)
            realjid = app.get_jid_from_account(account)
            realjid = app.get_jid_without_resource(str(realjid))
            if account:
                stanza_send = nbxmpp.Presence(to=jid, typ='subscribe', frm=realjid)
                app.connections[account].connection.send(stanza_send, now=True)
            return

        def on_cancel():
            return

        name = obj.jid
        reason = obj.stanza.getTag('invite').getTag('reason').getData()
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
        # TODO carbons
        '''
        <message to="maksim.batyatin@redsolution.com/gajim.42SK1ULX" from="maksim.batyatin@redsolution.com" type="chat">
           <sent xmlns="urn:xmpp:carbons:2">
              <forwarded xmlns="urn:xmpp:forward:0">
                 <message xmlns="jabber:client" xml:lang="en" to="4test@xmppdev01.xabber.com" from="maksim.batyatin@redsolution.com/xabber-web-7822b4e5-3f6c-4f61" type="chat" id="3b77dae1-7a2a-4fbb-9353-09bf6cd4578e">
                    <archived xmlns="urn:xmpp:mam:tmp" by="maksim.batyatin@redsolution.com" id="1537945809408098" />
                    <stanza-id xmlns="urn:xmpp:sid:0" by="maksim.batyatin@redsolution.com" id="1537945809408098" />
                    <markable xmlns="urn:xmpp:chat-markers:0" />
                    <origin-id xmlns="urn:xmpp:sid:0" id="3b77dae1-7a2a-4fbb-9353-09bf6cd4578e" />
                    <body>test</body>
                 </message>
              </forwarded>
           </sent>
        </message>
        '''
        room = obj.jid
        addallowjid(room)
        stanza_id = obj.stanza.getTag('stanza-id').getAttr('id')
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

        forwarded = obj.stanza.getTag('origin-id', namespace='urn:xmpp:sid:0').getTag('forwarded',
                                                                                      namespace='urn:xmpp:forward:0')
        forward_m = None
        if forwarded:
            print('forwarded\n'*10)
            delay = forwarded.getTag('delay', namespace='urn:xmpp:delay').getAttr('stamp')
            fobj = forwarded.getTag('message')
            fstanza_id = fobj.getTag('stanza-id').getAttr('id')

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
                         'ts': delay,
                         'stanza_id': fstanza_id
            }

        obj.additional_data.update({'jid': jid,
                                    'nickname': name,
                                    'message': message,
                                    'id': userid,
                                    'av_id': id,
                                    'role': role,
                                    'badge': badge,
                                    'forward': forward_m,
                                    'ts': datetime.datetime.now().isoformat(),
                                    'stanza_id': stanza_id
                                    })
        myjid = obj.stanza.getAttr('to')
        account = get_account_from_jid(myjid)
        if id != 'unknown' and account:
            self.send_call_single_avatar(account, room, userid, id)

    @log_calls('XabberGroupsPlugin')
    def send_call_single_avatar(self, account, room, u_id, av_id, stanza_id=''):
        try:
            # error if avatar is not exist
            dir = AVATARS_DIR + '/' + av_id + '.jpg'
            k = open(os.path.normpath(dir))
            return True
        except:
            stanza_send = nbxmpp.Iq(to=room, typ='get')
            stanza_send.setAttr('id', stanza_id)
            stanza_send.setTag('pubsub').setNamespace('http://jabber.org/protocol/pubsub')
            stanza_send.getTag('pubsub').setTagAttr('items', 'node', ('urn:xmpp:avatar:data#'+str(u_id)))
            stanza_send.getTag('pubsub').getTag('items').setTagAttr('item', 'id', str(av_id))
            app.connections[account].connection.send(stanza_send, now=True)
            return False

    @log_calls('XabberGroupsPlugin')
    def send_ask_for_pinned_message(self, myjid, room, pinned_id):
        '''
        <iq type='set' to='juliet@capulet.lit’ id='juliet1'>
            <query xmlns='urn:xmpp:mam:2'>
                <x xmlns='jabber:x:data' type='submit'>
                    <field var='FORM_TYPE' type='hidden'>
                        <value>urn:xmpp:mam:2</value>
                    </field>
                    <field var='{urn:xmpp:sid:0}stanza-id'>
                        <value>25475679764576348745</value>
                    </field>
                </x>
            </query>
        </iq>

        item = stanza_send.getTag('query').getTag('item').addChild('restriction')
        '''
        stanza_send = nbxmpp.Iq(to=room, typ='set')
        stanza_send.setAttr('id', 'XGCPinnedMessage')

        if pinned_id:
            stanza_send.setTag('query').setNamespace('urn:xmpp:mam:2')
            stanza_send.getTag('query').setTag('x').setNamespace('jabber:x:data')
            stanza_send.getTag('query').getTag('x').setAttr('type', 'submit')

            field = stanza_send.getTag('query').getTag('x').addChild('field')
            field.setAttr('var', 'FORM_TYPE')
            field.setAttr('type', 'hidden')
            field.setTag('value').setData('urn:xmpp:mam:2')

            field2 = stanza_send.getTag('query').getTag('x').addChild('field')
            field2.setAttr('var', '{urn:xmpp:sid:0}stanza-id')
            field2.setTag('value').setData(str(pinned_id))

        # in this case we ask to delete pinned message
        else:
            stanza_send.setTag('update', namespace='http://xabber.com/protocol/groupchat').setTag('pinned-message')

        account = get_account_from_jid(myjid)
        app.connections[account].connection.send(stanza_send, now=True)


    @log_calls('XabberGroupsPlugin')
    def connect_with_chat_control(self, chat_control):
        account = chat_control.contact.account.name
        room = chat_control.contact.jid
        acc_jid = app.get_jid_from_account(account)

        if room in allowjids:
            # if jid in allowjids:  # ask for rights if xgc if open chat control
            if account not in self.controls:
                self.controls[account] = {}
            self.controls[account][room] = Base(self, chat_control.conv_textview, chat_control)

            # check if user data is already exist
            # if its not, ask for user data
            try:
                is_data_exist = self.userdata[room][acc_jid]['av_id']
                self.controls[account][room].on_userdata_updated(self.userdata[room][acc_jid])
                self.send_ask_history_when_connect(room, acc_jid)
            except:
                self.send_ask_for_rights(acc_jid, room, type='XGCUserdata')

            if room in self.room_data:
                if self.room_data[room]['pinned']:
                    self.send_ask_for_pinned_message(acc_jid, room, self.room_data[room]['pinned'])

    @log_calls('XabberGroupsPlugin')
    def disconnect_from_chat_control(self, chat_control):
        account = chat_control.contact.account.name
        jid = chat_control.contact.jid
        self.controls[account][jid].deinit_handlers()
        del self.controls[account][jid]

    @log_calls('XabberGroupsPlugin')
    def print_real_text(self, tv, real_text, text_tags, graphics,
                        iter_, additional_data):
        account = tv.account
        for jid in self.controls[account]:
            if self.controls[account][jid].textview != tv:
                continue
            self.controls[account][jid].print_real_text(
                real_text, text_tags, graphics, iter_, additional_data)
            return



class Base(object):

    def __init__(self, plugin, textview, chat_control):
        # recieve textview to work with
        self.cli_jid = app.get_jid_from_account(chat_control.contact.account.name)
        self.room_jid = chat_control.contact.jid

        self.top_message_id = None
        self.is_waiting_for_messages = True
        self.xmam_loc_id = 0

        self.plugin = plugin
        self.textview = textview
        self.handlers = {}
        self.chat_control = chat_control
        self.default_avatar = os.path.join(os.path.dirname(os.path.abspath(__file__)), "default.png")
        # self.default_avatar = base64.encodestring(open(default_avatar, "rb").read())

        self.previous_message_from = None
        self.last_message_date = None
        self.current_message_id = -1
        self.chosen_messages_data = []

        self.box = Gtk.Box(False, 0, orientation=Gtk.Orientation.VERTICAL)
        #self.box.set_size_request(self.textview.tv.get_allocated_width(), self.textview.tv.get_allocated_height())
        self.scrolled = Gtk.ScrolledWindow()
        self.scrolled.add(self.box)
        '''
        self.box = Gtk.Box(False, 0, orientation=Gtk.Orientation.VERTICAL)
        self.scrolled = Gtk.ScrolledWindow()
        chatc_control_box = chat_control.xml.get_object('vbox2')
        # chatc_control_box.add(self.box)
        chatc_control_box.pack_start(self.scrolled, True, True, 0)
        chatc_control_box.reorder_child(self.box, 2)'''
        self.textview.tv.connect_after('size-allocate', self.resize)

        self.textview.tv.add(self.scrolled)
        self.scrolled.size_allocate(self.textview.tv.get_allocation())
        self.scrolled.connect_after('edge-reached', self.scrolled_changed)

        self.create_buttons(self.chat_control)

    def scrolled_changed(self, widg, pos):
        if (Gtk.PositionType(2) == pos) and not self.is_waiting_for_messages:
            # todo ask for prevous messages
            # self.top_message_id
            self.last_message_date = None
            self.plugin.send_ask_for_hisrory_when_top_reached(self.room_jid, self.cli_jid, self.top_message_id)
            # send ask for prev messages
            self.is_waiting_for_messages = True

    def resize(self, widget, r):
        self.normalize_action_hbox()
        self.scrolled.set_size_request(r.width, r.height)
        messages = [m for m in self.box.get_children()]
        for i in messages:
            try:
                j = i.get_children()
                j[2].set_size_request(r.width - (64+95), -1)
            except: pass

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


    def print_message(self, SAME_FROM, nickname, message, role, badge, additional_data, timestamp, mam_loc):

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

        self.box.pack_start(simplegrid, False, False, 0)
        if mam_loc:
            self.box.reorder_child(simplegrid, self.xmam_loc_id)
            self.xmam_loc_id+=1
        # set size of message by parent width after creating
        self.do_resize(simplegrid)
        simplegrid.show_all()

    def print_server_info(self, real_text, mam_loc=False):
        server_info = Gtk.Label(real_text)
        css = '''#server_info {
        padding: 8px 0px;
        font-size: 12px;
        color: #9E9E9E;}'''
        gtkgui_helpers.add_css_to_widget(server_info, css)
        server_info.set_name('server_info')
        self.box.pack_start(server_info, False, False, 0)
        server_info.show_all()
        if mam_loc:
            self.box.reorder_child(server_info, self.xmam_loc_id)
            self.xmam_loc_id += 1

    def print_real_text(self, real_text, text_tags, graphics, iter_, additional_data, mam_loc=False):

        print(additional_data)
        print(text_tags)

        # delete old text from textview
        if iter_:
            buffer_ = self.textview.tv.get_buffer()
            self.textview.plugin_modified = True
            start = buffer_.get_start_iter()
            end = buffer_.get_end_iter()
            buffer_.delete(start, end)

        # restored_message
        # need to ignore it
        is_not_history = True
        if 'restored_message' in text_tags:
            is_not_history = False
            print('yes, i am restored\n'
                  'you dont need me\n'
                  'so, i am leaving you')

        if is_not_history:
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
                    self.print_server_info(dt.strftime("%A, %d %B, %Y"), mam_loc)

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


            if IS_MSG:
                self.print_message(SAME_FROM, nickname, message, role, badge, additional_data, timestamp, mam_loc)
            else:
                self.print_server_info(real_text)

            if not mam_loc:
                gtkgui_helpers.scroll_to_end(self.scrolled)




    def on_avatar_press_event(self, eb, event, additional_data=None):
        if not additional_data:
            additional_data = self.plugin.userdata[self.room_jid][self.cli_jid]

        # left click
        if event.type == Gdk.EventType.BUTTON_PRESS and event.button == 1:
            u_id = additional_data['id']
            self.plugin.send_ask_for_rights(self.cli_jid, room=self.room_jid,
                                            id=u_id, type='XGCUserOptions')

        # right klick
        elif event.type == Gdk.EventType.BUTTON_PRESS and event.button == 3:
            return

    def on_upload_avatar_dialog(self, eb, event, additional_data=None):
        if not additional_data:
            additional_data = self.plugin.userdata[self.room_jid][self.cli_jid]
        u_id = additional_data['id']

        dialog = Gtk.FileChooserDialog(_('Choose an avatar'), None,
                                       Gtk.FileChooserAction.OPEN,
                                       (Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
                                        Gtk.STOCK_OPEN, Gtk.ResponseType.OK))
        filter_text = Gtk.FileFilter()
        filter_text.set_name("jpeg avatar")
        filter_text.add_mime_type("image/jpeg")
        dialog.add_filter(filter_text)
        response = dialog.run()
        if response == Gtk.ResponseType.OK:
            print("Open clicked")
            avatar_base, av_hash = self.plugin.img_to_base64(dialog.get_filename())
            # send avatar base64
            self.plugin.send_publish_avatar_data(avatar_base, av_hash, self.room_jid, self.cli_jid, u_id)
        elif response == Gtk.ResponseType.CANCEL:
            print("Cancel clicked")
        dialog.destroy()

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

                if len(self.chosen_messages_data) == 1:
                    self.button_pin.show()
                else:
                    self.button_pin.hide()

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

        if len(self.chosen_messages_data) == 1:
            self.button_pin.show()
        else:
            self.button_pin.hide()

    def on_userdata_updated(self, userdata = None):
        self.show_xbtn_hide_othr()
        self.remove_message_selection()
        if userdata:
            self.update_user_avatar(userdata['av_id'])

    def update_user_avatar(self, av_id):
        try:
            path = os.path.normpath(AVATARS_DIR + '/' + av_id + '.jpg')
            file = open(path)
            file = os.path.normpath(path)
            css = '''        
            #XCAvatar {
            padding: 0px 8px;
            }'''
            av_pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(file, 48, 48, False)
            av_image = Gtk.Image.new_from_pixbuf(av_pixbuf)
            gtkgui_helpers.add_css_to_widget(av_image, css)
            av_image.set_name('XCAvatar')

            # update avatar
            for child in self.user_avatar.get_children():
                self.user_avatar.remove(child)
            self.user_avatar.add(av_image)
            av_image.show()
            self.user_avatar.show()
        except:
            return

    def create_buttons(self, chat_control):

        # ========================== chat text editor ========================== #
        self.actions_hbox = chat_control.xml.get_object('hbox')

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
        #XCAvatar {
        padding: 0px 8px;
        }
        #GCTextEditor{
        border-bottom: 2px solid #D32F2F;
        }
        '''

        # very dangerous because of position can be changed
        self.text_editor = self.actions_hbox.get_children()[2]
        gtkgui_helpers.add_css_to_widget(self.text_editor, css)
        self.text_editor.set_name('GCTextEditor')

        self.user_avatar = Gtk.EventBox()
        self.user_avatar.connect('button-press-event', self.on_avatar_press_event)
        av_pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(self.default_avatar, 48, 48, False)
        av_image = Gtk.Image.new_from_pixbuf(av_pixbuf)
        gtkgui_helpers.add_css_to_widget(av_image, css)
        av_image.set_name('XCAvatar')
        self.user_avatar.add(av_image)

        # buttons configs

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

        self.button_copy = Gtk.Button(label='COPY', stock=None, use_underline=False)
        self.button_copy.set_tooltip_text(_('copy text from messages widgets (press ctrl+v to paste it)'))
        id_ = self.button_copy.connect('clicked', self.on_copytext_clicked)
        chat_control.handlers[id_] = self.button_copy
        gtkgui_helpers.add_css_to_widget(self.button_copy, css)
        self.button_copy.set_name('XCbutton')

        self.button_pin = Gtk.Button(label='PIN', stock=None, use_underline=False)
        self.button_pin.set_tooltip_text(_('pin message'))
        id_ = self.button_pin.connect('clicked', self.on_pin_clicked)
        chat_control.handlers[id_] = self.button_pin
        gtkgui_helpers.add_css_to_widget(self.button_pin, css)
        self.button_pin.set_name('XCbutton')

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
        self.button_pin.get_style_context().add_class('chatcontrol-actionbar-button')

        self.buttongrid = Gtk.Grid()
        self.buttongrid.attach(self.button_forward, 0, 0, 1, 1)
        self.buttongrid.attach(self.button_reply, 1, 0, 1, 1)
        self.buttongrid.attach(self.button_copy, 2, 0, 1, 1)
        self.buttongrid.attach(self.button_pin, 3, 0, 1, 1)
        #self.buttongrid.attach(self.button_cancel, 4, 0, 1, 1)

        self.buttonbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        self.buttonbox.pack_start(self.buttongrid, True, True, 0)
        self.buttonbox.pack_start(self.button_cancel, False, False, 0)

        self.actions_hbox.pack_start(self.buttonbox, True, True, 0)
        self.actions_hbox.pack_start(self.button_cancel, True, True, 0)
        self.actions_hbox.pack_start(self.user_avatar, False, False, 0)
        self.actions_hbox.reorder_child(self.user_avatar, 0)

        self.button_copy.set_size_request(95, 35)
        self.button_forward.set_size_request(95, 35)
        self.button_reply.set_size_request(95, 35)
        self.button_cancel.set_size_request(95, 35)
        self.button_pin.set_size_request(95, 35)

        # clear? seems like it doesn't work!
        self.hide_all_actions()
        self.normalize_action_hbox()

        # ========================== chat xgc menu ========================== #
        css_button = '''
        #XGCmenubutton{
        margin: 6px 2px;
        padding: 0 10px;
        color: #9E9E9E;
        background-color: #FFFFFF;
        background: #FFFFFF;
        border: none;
        border-radius: 2px;
        font-size: 22px;
        font-weight: bold;
        opacity: 0.4;
        }
        #XGCmenubutton:hover{
        color: #616161;
        opacity: 0.7;
        }
        '''

        topmenu = chat_control.xml.get_object('hbox3004')
        group_chat_menubutton = Gtk.Button()
        file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'icons')
        file = os.path.join(file, 'icon-menu-alt.png')
        pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(file, 16, 16, False)
        image = Gtk.Image.new_from_pixbuf(pixbuf)
        group_chat_menubutton.add(image)
        group_chat_menubutton.connect('clicked', self.do_open_chat_editor_dialog)
        topmenu.add(group_chat_menubutton)

        group_chat_add_user = Gtk.Button()
        file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'icons')
        file = os.path.join(file, 'icon-add-user.png')
        pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(file, 16, 16, False)
        image = Gtk.Image.new_from_pixbuf(pixbuf)
        group_chat_add_user.add(image)
        group_chat_add_user.connect('clicked', self.do_invite_member_dialog)
        topmenu.add(group_chat_add_user)

        group_chat_menubutton.set_size_request(48, -1)
        group_chat_add_user.set_size_request(48, -1)
        gtkgui_helpers.add_css_to_widget(group_chat_menubutton, css_button)
        group_chat_menubutton.set_name('XGCmenubutton')
        gtkgui_helpers.add_css_to_widget(group_chat_add_user, css_button)
        group_chat_add_user.set_name('XGCmenubutton')

        # ========================== pinned message  ========================== #

        self.pinned_message = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)

        pinned_name_badge_role = Gtk.Grid()
        self.pinned_nick = Gtk.Label('nickname')
        css = '''#info_name {
        color: #D32F2F;
        font-size: 12px;
        margin-right: 4px;
        margin-top: 10px;}'''
        gtkgui_helpers.add_css_to_widget(self.pinned_nick, css)
        self.pinned_nick.set_name('info_name')

        self.pinned_datetime = Gtk.Label('September 18, datetime ok da')
        css = '''#info_ts {
        margin-top: 10px;
        font-size: 12px;
        color: #666;}'''
        gtkgui_helpers.add_css_to_widget(self.pinned_datetime, css)
        self.pinned_datetime.set_name('info_ts')

        pinned_name_badge_role.attach(self.pinned_nick, 0, 0, 1, 1)
        pinned_name_badge_role.attach(self.pinned_datetime, 1, 0, 1, 1)

        self.pinned_message_text = Gtk.Label('message text ok da')
        css = '''#message_font_size {
        font-size: 12px;
        margin-top: 6px;
        margin-bottom: 8px;}'''
        gtkgui_helpers.add_css_to_widget(self.pinned_message_text, css)
        self.pinned_message_text.set_name('message_font_size')
        self.pinned_message_text.set_line_wrap(True)
        self.pinned_message_text.set_justify(Gtk.Justification.LEFT)
        self.pinned_message_text.set_halign(Gtk.Align.START)
        self.pinned_message_text.set_ellipsize(Pango.EllipsizeMode.END)
        pinned_message_text_grid = Gtk.Grid()
        pinned_message_text_grid.add(self.pinned_message_text)

        al_pinned_data = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        al_pinned_data.pack_start(pinned_name_badge_role, False, False, 0)
        al_pinned_data.pack_start(pinned_message_text_grid, False, False, 0)

        pinlabel = Gtk.Label(u"\U0001F4CC")
        pinlabel.set_size_request(64, 54)
        pinbutton = Gtk.Button(u"\u2A2F")
        pinbutton.connect('clicked', self.send_unpin_message)
        pinbutton.set_size_request(34, 34)
        pinbutton.set_margin_left(10)
        pinbutton.set_margin_right(10)
        pinbutton.set_margin_top(10)
        pinbutton.set_margin_bottom(10)
        gtkgui_helpers.add_css_to_widget(pinbutton, css_button)
        pinbutton.set_name('XGCmenubutton')

        hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        hbox.pack_start(pinlabel, False, False, 0)
        hbox.pack_start(al_pinned_data, False, False, 0)

        self.pinned_message.pack_start(hbox, True, True, 0)
        self.pinned_message.pack_start(pinbutton, False, False, 0)
        chat_control_box = chat_control.xml.get_object('vbox2')
        chat_control_box.add(self.pinned_message)
        chat_control_box.reorder_child(self.pinned_message, 1)

        self.pinned_message.hide()

    def send_unpin_message(self, widget):
        # def send_ask_for_pinned_message(self, myjid, room, pinned_id):
        self.plugin.send_ask_for_pinned_message(self.cli_jid, self.room_jid, None)
        return

    def set_pin_message(self, name, timestamp, message):
        self.pinned_nick.set_text(name)
        self.pinned_datetime.set_text(timestamp)
        self.pinned_message_text.set_text(message.replace('\n', ' '))
        self.pinned_message.show()

    def set_unpin_message(self):
        self.pinned_nick.set_text('')
        self.pinned_datetime.set_text('')
        self.pinned_message_text.set_text('')
        self.pinned_message.hide()

    def do_invite_member_dialog(self, widget):
        dialog = InviteMemberDialog(self, self.plugin, allowjids, self.default_avatar)
        response = dialog.popup()

    def do_open_chat_editor_dialog(self, widget):
        if not self.room_jid in self.plugin.chat_edit_dialog_windows:
            dialog = ChatEditDialog(self, self.plugin, self.default_avatar)
            response = dialog.popup()

    def remove_message_selection(self, w=None):
        print('remove_message_selection')
        self.chosen_messages_data = []
        self.show_othr_hide_xbtn()
        messages = [m for m in self.box.get_children()]
        for widget in messages:
            css = '''#messagegrid {
            background-color: #FFFFFF;}'''
            gtkgui_helpers.add_css_to_widget(widget, css)

    def normalize_action_hbox(self):
        settings_menu = self.chat_control.xml.get_object('settings_menu')
        encryption_menu = self.chat_control.xml.get_object('encryption_menu')
        formattings_button = self.chat_control.xml.get_object('formattings_button')
        settings_menu.hide()
        encryption_menu.hide()
        formattings_button.hide()

        if self.chosen_messages_data == []:
            self.show_othr_hide_xbtn()
        else:
            self.show_xbtn_hide_othr()

    def hide_all_actions(self):
        settings_menu = self.chat_control.xml.get_object('settings_menu')
        encryption_menu = self.chat_control.xml.get_object('encryption_menu')
        formattings_button = self.chat_control.xml.get_object('formattings_button')
        settings_menu.hide()
        encryption_menu.hide()
        formattings_button.hide()
        emoticons_button = self.chat_control.xml.get_object('emoticons_button')
        sendfile_button = self.chat_control.xml.get_object('sendfile_button')
        emoticons_button.hide()
        sendfile_button.hide()
        self.text_editor.hide()
        self.user_avatar.hide()
        self.buttonbox.hide()

    def show_xbtn_hide_othr(self):
        settings_menu = self.chat_control.xml.get_object('settings_menu')
        encryption_menu = self.chat_control.xml.get_object('encryption_menu')
        formattings_button = self.chat_control.xml.get_object('formattings_button')
        settings_menu.hide()
        encryption_menu.hide()
        formattings_button.hide()

        emoticons_button = self.chat_control.xml.get_object('emoticons_button')
        sendfile_button = self.chat_control.xml.get_object('sendfile_button')
        emoticons_button.hide()
        sendfile_button.hide()
        self.text_editor.hide()
        self.user_avatar.hide()
        self.buttonbox.show()

    def show_othr_hide_xbtn(self):
        emoticons_button = self.chat_control.xml.get_object('emoticons_button')
        sendfile_button = self.chat_control.xml.get_object('sendfile_button')
        emoticons_button.show()
        sendfile_button.show()
        self.text_editor.show()
        self.user_avatar.show()
        self.buttonbox.hide()

    def on_pin_clicked(self, widget):
        data = self.chosen_messages_data[0]
        self.remove_message_selection()
        print('pin clicked')
        print(data)
        stanza_id = data[1]['forward']
        if stanza_id:
            stanza_id = data[1]['forward']['stanza_id']
        else:
            stanza_id = data[1]['stanza_id']

        self.plugin.send_set_pinned_message(self.room_jid, self.cli_jid, stanza_id)



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
            finally:
                copied_text += ''
        clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
        clipboard.set_text(copied_text, -1)
        self.remove_message_selection()

    def on_forward_clicked(self, widget):
        print('forward clicked!')

    def on_reply_clicked(self, widget):
        print('reply clicked!')
