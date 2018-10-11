import gi
import os
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gdk, GdkPixbuf, Pango
from gajim import gtkgui_helpers
from gajim.common import app
from gajim.common import configpaths

class UserDataDialog(Gtk.Dialog):

    def __init__(self, plugin, userdata, image, chat_control):
        self.plugin = plugin
        self.chat_control = chat_control

        self.userdata = userdata
        self.self_userdata = plugin.userdata[chat_control.room_jid][chat_control.cli_jid]

        nickname_text = userdata['nickname']
        badge_text = userdata['badge']
        if userdata['jid'] == 'Unknown':
            user_id = userdata['id']
        else: user_id = userdata['jid']

        Gtk.Dialog.__init__(self, nickname_text, None, 0)

        self.can_edit = False
        self.can_kick = False
        self.can_block = False
        self.is_owner = False

        self.isme = False
        if self.userdata['id'] == self.self_userdata['id']:
            self.isme = True

        if 'owner' in self.self_userdata['rights']['permissions']:
            self.is_owner = True
        if 'remove-member' in self.self_userdata['rights']['permissions']:
            self.can_kick = False
        if 'block-member' in self.self_userdata['rights']['permissions']:
            self.can_block = True
        a = ['change-badge', 'change-nickname', 'change-restriction']
        if list(set(a) & set(self.self_userdata['rights']['permissions'])) or self.isme:
            self.can_edit = True


        self.set_default_size(480, 480)
        self.rights = {}
        self.switches = {}

        # =========================== header ============================= #
        css = '''
        #user_jid_id{
        font-size: 12px;
        color: #9E9E9E;
        }
        '''

        header_grid = Gtk.Grid()
        header_grid.set_margin_bottom(20)
        self.avatar = Gtk.EventBox()
        self.avatar.connect('button-press-event', chat_control.on_upload_avatar_dialog, userdata)
        self.avatar.add(image)
        self.avatar.set_margin_left(20)
        self.avatar.set_margin_right(20)
        self.avatar.set_margin_top(10)
        self.avatar.set_size_request(40, 40)

        self.nickname = Gtk.Entry()
        self.nickname.set_placeholder_text(_('nickname'))
        self.nickname.set_text(nickname_text)
        self.nickname.set_margin_top(10)
        self.nickname.set_size_request(48, -1)

        if 'change-nickname' in self.self_userdata['rights']['permissions'] or self.is_owner or self.isme:
            self.nickname.set_editable(True)
        else:
            self.nickname.set_editable(False)

        self.badge = Gtk.Entry()
        self.badge.set_placeholder_text(_('badge'))
        self.badge.set_text(badge_text)
        self.badge.set_margin_left(10)
        self.badge.set_margin_right(10)
        self.badge.set_margin_top(10)
        self.badge.set_size_request(32, -1)

        if 'change-badge' in self.self_userdata['rights']['permissions'] or self.is_owner:
            self.badge.set_editable(True)
        else:
            self.badge.set_editable(False)

        emoticonbutton = Gtk.Button(u"\u263B")
        emoticonbutton.set_margin_top(10)
        emoticonbutton.set_margin_right(20)
        emoticonbutton.set_size_request(32, -1)

        namebadge_grid = Gtk.Grid()
        namebadge_grid.attach(self.nickname, 0, 0, 1, 1)
        namebadge_grid.attach(self.badge, 1, 0, 1, 1)
        namebadge_grid.attach(emoticonbutton, 2, 0, 1, 1)

        jid_id = Gtk.TextView()
        jid_id.get_buffer().set_text(user_id)
        gtkgui_helpers.add_css_to_widget(jid_id, css)
        jid_id.set_name('user_jid_id')
        jid_id.set_editable(False)
        jid_id_grid = Gtk.Grid()
        jid_id_grid.add(jid_id)

        header_grid.attach(self.avatar, 0, 0, 1, 2)
        header_grid.attach(namebadge_grid, 1, 0, 1, 1)
        header_grid.attach(jid_id_grid, 1, 1, 1, 1)
        # =========================== end header ============================= #

        # =========================== list of rights ============================= #
        # rights listbox
        # scrolled = Gtk.ScrolledWindow()
        # scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        # scrolled.set_size_request(-1, 400)
        scrolled = Gtk.ScrolledWindow()
        listbox = Gtk.ListBox()
        listbox.set_selection_mode(Gtk.SelectionMode.NONE)
        scrolled.add(listbox)

        def addrow(name, state, expires='Not able'):

            text = name
            text = text.capitalize().replace('-', ' ')
            row = Gtk.ListBoxRow()
            hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=50)
            hbox.set_margin_left(20)
            hbox.set_margin_right(20)
            row.add(hbox)
            vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
            hbox.pack_start(vbox, True, True, 0)
            label1 = Gtk.Label(text, xalign=0)
            label2 = Gtk.Label(expires, xalign=0)
            css = '''#expires {
            font-size: 12px;
            color: #666;}'''
            gtkgui_helpers.add_css_to_widget(label2, css)
            label2.set_name('expires')
            vbox.pack_start(label1, True, True, 0)
            vbox.pack_start(label2, True, True, 0)
            switch = Gtk.Switch()
            switch.props.valign = Gtk.Align.CENTER
            switch.set_state(state)
            hbox.pack_start(switch, False, True, 0)

            self.rights[name] = state
            self.switches[name] = switch

            return row

        # welcome to india, lets dance!
        # India ends, sorry but that was fun :)
        RestLabel = Gtk.Label('Restrictions')
        RestLabel.set_margin_bottom(10)
        RestLabel.set_margin_top(10)
        listbox.add(RestLabel)
        res = userdata['rights']['restrictions']

        for i in ['read', 'send-audio', 'send-image', 'write']:
            if i in res:
                row = addrow(i, True, res[i][0])
                row.set_margin_top(8)
                listbox.add(row)
            else:
                row = addrow(i, False)
                row.set_margin_top(8)
                listbox.add(row)

        PermLabel = Gtk.Label('Permissions')
        PermLabel.set_margin_bottom(10)
        PermLabel.set_margin_top(10)
        listbox.add(PermLabel)
        res = userdata['rights']['permissions']

        for i in ['owner', 'block-member', 'change-badge', 'change-chat',
                'change-nickname', 'change-restriction', 'invite-member', 'remove-member']:
            if i in res:
                row = addrow(i, True, res[i][0])
                row.set_margin_top(8)
                listbox.add(row)
            else:
                row = addrow(i, False)
                row.set_margin_top(8)
                listbox.add(row)
        # =========================== end list of rights ============================= #

        # =========================== buttons at the bottom ============================= #

        button_hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=50)
        button_hbox.set_margin_top(20)
        button_hbox.set_margin_bottom(10)
        button_hbox.set_margin_left(20)
        button_hbox.set_margin_right(20)
        leftgrid = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        rightgrid = Gtk.Box()
        button_hbox.pack_start(leftgrid, True, True, 0)
        button_hbox.pack_start(rightgrid, False, True, 0)
        button_hbox.set_size_request(-1, 36)

        # css is coming
        css = '''
        #Xbutton-blackfont {
        color: #212121;
        margin: 0 5px;
        padding: 0 10px;
        background-color: #FFFFFF;
        background: #FFFFFF;
        border: none;
        border-radius: 2px;
        font-size: 13px;
        font-weight: bold;
        }
        #Xbutton-redfont {
        color: #D32F2F;
        margin: 0 5px;
        padding: 0 10px;
        background-color: #FFFFFF;
        background: #FFFFFF;
        border: none;
        border-radius: 2px;
        font-size: 13px;
        font-weight: bold;
        }
        #Xbutton-blackfont:hover, #Xbutton-redfont:hover{
        background-color: #E0E0E0;
        background: #E0E0E0;
        }
        '''

        btn_kick = Gtk.Button(_('KICK'))
        btn_kick.connect('button-press-event', self.on_kick_clicked)
        btn_block = Gtk.Button(_('BLOCK'))
        btn_block.connect('button-press-event', self.on_block_clicked)
        btn_save = Gtk.Button(_('SAVE'))
        btn_save.connect('button-press-event', self.on_save_clicked)
        btn_kick.set_margin_right(10)

        gtkgui_helpers.add_css_to_widget(btn_kick, css)
        btn_kick.set_name('Xbutton-blackfont')
        gtkgui_helpers.add_css_to_widget(btn_block, css)
        btn_block.set_name('Xbutton-blackfont')
        gtkgui_helpers.add_css_to_widget(btn_save, css)
        btn_save.set_name('Xbutton-redfont')



        if self.can_edit or self.is_owner:
            rightgrid.pack_start(btn_save, False, True, 0)
        if (self.can_kick or self.is_owner) and not 'owner' in self.userdata['rights']['permissions']:
            leftgrid.pack_start(btn_kick, False, True, 0)
        if self.can_block or self.is_owner:
            leftgrid.pack_start(btn_block, False, True, 0)

        # =========================== end buttons at the bottom ============================= #

        box = self.get_content_area()
        css = '''#box_content_area {
        background-color: #FFFFFF;}'''
        gtkgui_helpers.add_css_to_widget(box, css)
        box.set_name('box_content_area')
        box.pack_start(header_grid, False, True, 0)
        box.pack_start(scrolled, True, True, 0)
        box.pack_start(button_hbox, False, True, 0)
        self.show_all()

    def on_save_clicked(self, eb, event):

        # =========================== if rights changed =========================== #
        new_userdata = {'restrictions': {},
                        'permissions': {}}

        # for right in rights_list:
        #    if right has changed:
        #        add it to changed-list
        for rest in ['read', 'send-audio', 'send-image', 'write']:
            if (rest in self.userdata['rights']['restrictions']) != self.switches[rest].get_state():
                new_userdata['restrictions'][rest] = self.switches[rest].get_state()
                print(rest, self.switches[rest].get_state())

        for perm in ['owner', 'block-member', 'change-badge', 'change-chat',
                     'change-nickname', 'change-restriction', 'invite-member', 'remove-member']:
            if (perm in self.userdata['rights']['permissions']) != self.switches[perm].get_state():
                new_userdata['permissions'][perm] = self.switches[perm].get_state()
                print(perm, self.switches[perm].get_state())

        # if changed-list have got at least 1 change:
        #    ask for rights changing
        if len(new_userdata['restrictions']) > 0 or len(new_userdata['permissions']) > 0:
            self.plugin.send_set_user_rights(self.chat_control.cli_jid, self.chat_control.room_jid,
                                             self.userdata['id'], new_userdata)

        # =========================== if nickname changed =========================== #
        if (self.nickname.get_text() != self.userdata['nickname']) and (self.nickname.get_text().strip() != ''):
            self.plugin.send_set_user_name(self.chat_control.cli_jid, self.chat_control.room_jid,
                                           self.userdata['id'], self.nickname.get_text().strip())

        # =========================== if badge changed =========================== #
        if (self.badge.get_text() != self.userdata['badge']) and (self.badge.get_text().strip() != ''):
            self.plugin.send_set_user_badge(self.chat_control.cli_jid, self.chat_control.room_jid,
                                           self.userdata['id'], self.badge.get_text().strip())


        self.destroy()

    def on_kick_clicked(self, eb, event):
        print('kick')
        self.plugin.send_set_user_kick(self.chat_control.cli_jid, self.chat_control.room_jid, self.userdata['id'])
        self.destroy()
        return

    def on_block_clicked(self, eb, event):
        print('block')
        self.plugin.send_set_user_block(self.chat_control.cli_jid, self.chat_control.room_jid, self.userdata['id'])
        self.destroy()
        return

    def popup(self):
        vb = self.get_children()[0].get_children()[0]
        vb.grab_focus()
        self.show_all()


class CreateGroupchatDialog(Gtk.Dialog):
    def __init__(self, plugin):
        Gtk.Dialog.__init__(self, _('Add new group chat'), None, 0)
        self.set_default_size(400, 400)
        self.plugin = plugin

        # top label
        label_account = Gtk.Label('Account')
        label_account_grid = Gtk.Grid()
        label_account_grid.set_margin_bottom(10)
        label_account_grid.set_margin_top(10)
        label_account_grid.set_margin_left(20)
        label_account_grid.set_margin_right(20)
        label_account_grid.add(label_account)

        # account selector
        self.accounts_list = sorted(app.contacts.get_accounts())
        self.accounts_combo = Gtk.ComboBoxText()
        self.accounts_combo.set_entry_text_column(0)
        self.accounts_combo.set_margin_bottom(10)
        self.accounts_combo.set_margin_left(20)
        self.accounts_combo.set_margin_right(20)
        self.accounts_combo.set_size_request(-1, 44)
        if len(self.accounts_list):
            for acc in self.accounts_list:
                jid = app.get_jid_from_account(acc)
                self.accounts_combo.append_text(jid)
            self.accounts_combo.set_active(0)
        else:
            self.accounts_combo.append_text(_('No accounts'))
            self.accounts_combo.set_active(0)

        # groupchat name
        self.groupchat_name = Gtk.Entry()
        self.groupchat_name.set_placeholder_text(_('Group chat name'))
        self.groupchat_name.set_margin_bottom(10)
        self.groupchat_name.set_margin_left(20)
        self.groupchat_name.set_margin_right(20)
        self.groupchat_name.set_size_request(-1, 44)

        # group jid + @ + group server
        groupchat_jid_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        groupchat_jid_box.set_margin_bottom(10)
        groupchat_jid_box.set_margin_left(20)
        groupchat_jid_box.set_margin_right(20)
        self.groupchat_jid = Gtk.Entry()
        self.groupchat_jid.set_placeholder_text(_('Group Jid'))
        self.groupchat_jid.set_size_request(-1, 44)
        groupchat_jid_at = Gtk.Label('@xmppdev01.xabber.com')
        groupchat_jid_at.set_margin_left(8)
        groupchat_jid_at.set_size_request(-1, 44)
        groupchat_jid_box.pack_start(self.groupchat_jid, True, True, 0)
        groupchat_jid_box.pack_start(groupchat_jid_at, False, False, 0)

        # checkboxes is_anonimous and is_searchable
        self.checkbox_is_anonimous = Gtk.CheckButton.new_with_label(_('Anonymous'))
        self.checkbox_is_anonimous.set_active(False)
        self.checkbox_is_anonimous.set_size_request(-1, 32)
        self.checkbox_is_anonimous.set_margin_left(20)
        self.checkbox_is_anonimous.set_margin_right(20)

        self.checkbox_is_searchable = Gtk.CheckButton.new_with_label(_('Searchable'))
        self.checkbox_is_searchable.set_active(True)
        self.checkbox_is_searchable.set_size_request(-1, 32)
        self.checkbox_is_searchable.set_margin_left(20)
        self.checkbox_is_searchable.set_margin_right(20)

        self.checkbox_is_discoverable = Gtk.CheckButton.new_with_label(_('Discoverable'))
        self.checkbox_is_discoverable.set_active(True)
        self.checkbox_is_discoverable.set_size_request(-1, 32)
        self.checkbox_is_discoverable.set_margin_left(20)
        self.checkbox_is_discoverable.set_margin_right(20)

        self.checkbox_is_collect = Gtk.CheckButton.new_with_label(_('Collect avatars'))
        self.checkbox_is_collect.set_active(True)
        self.checkbox_is_collect.set_size_request(-1, 32)
        self.checkbox_is_collect.set_margin_left(20)
        self.checkbox_is_collect.set_margin_right(20)
        self.checkbox_is_collect.set_margin_bottom(10)

        # description
        self.description = Gtk.Entry()
        self.description.set_placeholder_text(_('Description'))
        self.description.set_size_request(-1, 44)
        self.description.set_margin_left(20)
        self.description.set_margin_right(20)
        self.description.set_margin_bottom(10)

        # open type or member only
        self.new_chat_model = Gtk.ComboBoxText()
        self.new_chat_model.set_entry_text_column(0)
        self.new_chat_model.set_margin_bottom(10)
        self.new_chat_model.set_margin_left(20)
        self.new_chat_model.set_margin_right(20)
        self.new_chat_model.set_size_request(-1, 44)
        self.new_chat_model.append_text('open')
        self.new_chat_model.append_text('member-only')
        self.new_chat_model.set_active(0)

        # buttons
        css = '''
        #Xbutton-blackfont {
        color: #212121;
        margin: 0 5px;
        padding: 0 10px;
        background-color: #FFFFFF;
        background: #FFFFFF;
        border: none;
        border-radius: 2px;
        font-size: 13px;
        font-weight: bold;
        }
        #Xbutton-redfont {
        color: #D32F2F;
        margin: 0 5px;
        padding: 0 10px;
        background-color: #FFFFFF;
        background: #FFFFFF;
        border: none;
        border-radius: 2px;
        font-size: 13px;
        font-weight: bold;
        }
        #Xbutton-blackfont:hover, #Xbutton-redfont:hover{
        background-color: #E0E0E0;
        background: #E0E0E0;
        }
        '''
        btn_cancel = Gtk.Button(_('CANCEL'))
        btn_cancel.connect('button-press-event', self.on_cancel_clicked)
        btn_add = Gtk.Button(_('ADD'))
        btn_add.connect('button-press-event', self.on_add_clicked)
        gtkgui_helpers.add_css_to_widget(btn_cancel, css)
        btn_cancel.set_name('Xbutton-blackfont')
        gtkgui_helpers.add_css_to_widget(btn_add, css)
        btn_add.set_name('Xbutton-redfont')

        button_hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=50)
        button_hbox.set_margin_bottom(10)
        button_hbox.set_margin_left(20)
        button_hbox.set_margin_right(20)
        leftgrid = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        rightgrid = Gtk.Box()
        leftgrid.pack_start(btn_cancel, False, True, 0)
        rightgrid.pack_start(btn_add, False, True, 0)
        button_hbox.pack_start(leftgrid, True, True, 0)
        button_hbox.pack_start(rightgrid, False, True, 0)
        button_hbox.set_size_request(-1, 36)

        box = self.get_content_area()
        box.add(label_account_grid)
        box.add(self.accounts_combo)
        box.add(self.groupchat_name)
        box.add(groupchat_jid_box)
        box.add(self.description)
        box.add(self.checkbox_is_anonimous)
        box.add(self.checkbox_is_searchable)
        box.add(self.checkbox_is_discoverable)
        box.add(self.checkbox_is_collect)
        box.add(self.new_chat_model)
        box.add(button_hbox)

    def on_cancel_clicked(self, eb, event):
        print('cancel')
        self.destroy()

    def on_add_clicked(self, eb, event):
        jid = self.accounts_combo.get_active_text()  # jid of current account
        new_chat_name = self.groupchat_name.get_text()  # name of chat
        room_jid = self.groupchat_jid.get_text()  # first part of jid of chat
        is_anonimous = self.checkbox_is_anonimous.get_active()
        is_searchable = self.checkbox_is_searchable.get_active()
        is_discoverable = self.checkbox_is_discoverable.get_active()
        is_collect_avs = self.checkbox_is_collect.get_active()
        description = self.description.get_text()  # text
        chat_model = self.new_chat_model.get_active_text()  # open / member-only
        print(jid)
        print(new_chat_name)
        print(room_jid)
        print(is_anonimous)
        print(is_searchable)
        print(description)
        print(chat_model)
        print('add')
        self.plugin.send_ask_for_create_group_chat(jid, {
            'name': new_chat_name,
            'jid': room_jid,
            'is_anon': is_anonimous,
            'is_search': is_searchable,
            'is_discov': is_discoverable,
            'is_collect': is_collect_avs,
            'desc': description,
            'access': chat_model
        })
        self.destroy()

    def popup(self):
        vb = self.get_children()[0].get_children()[0]
        vb.grab_focus()
        self.show_all()

class InviteMemberDialog(Gtk.Dialog):
    def __init__(self, chat_control, plugin, allowjids, default_avatar):
        gajimpaths = configpaths.gajimpaths
        self.AVATAR_PATH = gajimpaths['AVATAR']

        self.default_avatar = default_avatar
        self.chat_control = chat_control
        self.plugin = plugin
        Gtk.Dialog.__init__(self, _('Invite member'), None, 0)
        self.set_default_size(400, 600)

        self.CHOOSED_USERS = []
        self.user_widgets = []

        # ============================== search ============================== #
        self.search = Gtk.Entry()
        self.search.set_icon_from_icon_name(Gtk.EntryIconPosition.PRIMARY, 'system-search-symbolic')
        self.search.set_placeholder_text(_('Search'))
        self.search.set_margin_left(20)
        self.search.set_margin_right(20)
        self.search.set_margin_top(20)

        # ============================== scroll window ============================== #
        scrolled = Gtk.ScrolledWindow()
        listbox = Gtk.ListBox()
        listbox.set_selection_mode(Gtk.SelectionMode.NONE)
        scrolled.add(listbox)
        scrolled.set_margin_left(20)
        scrolled.set_margin_right(20)
        scrolled.set_margin_top(20)
        scrolled.set_margin_bottom(20)

        user_list = []

        account = None
        accounts = app.contacts.get_accounts()
        for acc in accounts:
            realjid = app.get_jid_from_account(acc)
            realjid = app.get_jid_without_resource(str(realjid))
            if self.chat_control.cli_jid == realjid:
                account = acc

        jids = app.contacts.get_contacts_jid_list(account)
        for jid in jids:
            jid = app.get_jid_without_resource(str(jid))
            if jid not in allowjids:
                contact = app.contacts.get_contact_with_highest_priority(account, jid)
                name = contact.get_shown_name()
                if not name:
                    name = jid
                if (name, jid) not in user_list:
                    avatar_sha = app.contacts.get_avatar_sha(account, jid)
                    user_list.append((name, jid, avatar_sha))


        for data in user_list:
            data_name = data[0]
            data_jid = data[1]
            avatar_sha = data[2]

            if avatar_sha:
                path = os.path.join(self.AVATAR_PATH, avatar_sha)
                pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(path, 32, 32, False)
                # pixbuf = Gdk.pixbuf_get_from_surface(pixbuf, 0, 0, 32, 32)
            else:
                pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(self.default_avatar, 32, 32, False)
            image = Gtk.Image.new_from_pixbuf(pixbuf)
            css = '''
                #xavatar {}
                    
                #user_jid{
                background: none;
                font-size: 11px;
                color: #9E9E9E;
                }
                #user_name{
                color: #212121;
                font-size: 16px;
                background: none;
                }
                '''
            gtkgui_helpers.add_css_to_widget(image, css)
            image.set_name('xavatar')

            name = Gtk.TextView()
            name.get_buffer().set_text(data_name)
            name.set_editable(False)
            gtkgui_helpers.add_css_to_widget(name, css)
            name.set_name('user_name')

            jid = Gtk.TextView()
            jid.get_buffer().set_text(data_jid)
            jid.set_editable(False)
            gtkgui_helpers.add_css_to_widget(jid, css)
            jid.set_name('user_jid')

            vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
            vbox.pack_start(name, False, True, 0)
            vbox.pack_start(jid, False, True, 0)

            hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=50)
            hbox.pack_start(image, False, False, 0)
            hbox.pack_start(vbox, False, False, 0)
            hbox.set_margin_top(4)
            hbox.set_margin_bottom(4)

            eventbox = Gtk.EventBox()
            eventbox.connect('button-press-event', self.on_user_clicked, eventbox, data_jid)
            eventbox.add(hbox)
            name.show()
            jid.show()
            vbox.show()
            eventbox.show()

            listbox.add(eventbox)
            self.user_widgets.append((eventbox, data_name, data_jid))



        # buttons
        css = '''
        #Xbutton-blackfont {
        color: #212121;
        margin: 0 5px;
        padding: 0 10px;
        background-color: #FFFFFF;
        background: #FFFFFF;
        border: none;
        border-radius: 2px;
        font-size: 13px;
        font-weight: bold;
        }
        #Xbutton-redfont {
        color: #D32F2F;
        margin: 0 5px;
        padding: 0 10px;
        background-color: #FFFFFF;
        background: #FFFFFF;
        border: none;
        border-radius: 2px;
        font-size: 13px;
        font-weight: bold;
        }
        #Xbutton-blackfont:hover, #Xbutton-redfont:hover{
        background-color: #E0E0E0;
        background: #E0E0E0;
        }
        '''
        btn_add = Gtk.Button(_('invite'))
        gtkgui_helpers.add_css_to_widget(btn_add, css)
        btn_add.set_name('Xbutton-redfont')
        btn_add.connect('button-press-event', self.send_invite)
        leftgrid = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        rightgrid = Gtk.Box()
        leftgrid.pack_start(Gtk.Label(''), True, True, 0)
        rightgrid.pack_start(btn_add, False, True, 0)

        button_hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        button_hbox.set_margin_bottom(10)
        button_hbox.set_margin_left(20)
        button_hbox.set_margin_right(20)
        button_hbox.set_size_request(-1, 36)

        button_hbox.pack_start(leftgrid, True, True, 0)
        button_hbox.pack_start(rightgrid, False, True, 0)

        self.reason = Gtk.Entry()
        self.reason.set_placeholder_text(_('Reason'))
        self.reason.set_margin_left(20)
        self.reason.set_margin_right(20)
        self.reason.set_margin_bottom(20)

        self.invite_by_chat = Gtk.CheckButton.new_with_label(_('Invite by group chat'))
        self.invite_by_chat.set_active(True)
        self.invite_by_chat.set_size_request(-1, 32)
        self.invite_by_chat.set_margin_left(20)
        self.invite_by_chat.set_margin_right(20)

        self.show_my_data = Gtk.CheckButton.new_with_label(_('Send my data'))
        self.show_my_data.set_size_request(-1, 32)
        self.show_my_data.set_margin_top(8)
        self.show_my_data.set_margin_left(20)
        self.show_my_data.set_margin_right(20)

        box = self.get_content_area()
        box.pack_start(self.search, False, True, 0)
        box.pack_start(scrolled, True, True, 0)
        box.pack_start(self.reason, False, True, 0)
        box.pack_start(self.invite_by_chat, False, True, 0)
        box.pack_start(self.show_my_data, False, True, 0)
        box.pack_start(button_hbox, False, True, 0)

        self.search.connect("changed", self.edit_changed)

    def edit_changed(self, widget):
        s = self.search.get_text()
        for widget in self.user_widgets:
            if s.lower() in widget[1].lower() or s.lower() in widget[2].lower():
                widget[0].show()
            else:
                widget[0].hide()

    def on_user_clicked(self, eb, event, widget, jid):
        css = '''
        #choosed {
        background-color: #FFCCCC;
        }
        #nonchoosed {}
        '''
        # left click
        if event.type == Gdk.EventType.BUTTON_PRESS and event.button == 1:
            if jid in self.CHOOSED_USERS:
                gtkgui_helpers.add_css_to_widget(widget, css)
                widget.set_name('nonchoosed')
                self.CHOOSED_USERS.remove(jid)
            else:
                gtkgui_helpers.add_css_to_widget(widget, css)
                widget.set_name('choosed')
                self.CHOOSED_USERS.append(jid)

    def send_invite(self, eb, event):
        invite_by_chat = self.invite_by_chat.get_active()
        send_my_data = self.show_my_data.get_active()
        reason = self.reason.get_text()
        to_jid = self.chat_control.room_jid
        from_jid = self.chat_control.cli_jid

        for jid in self.CHOOSED_USERS:
            invite_jid = jid
            self.plugin.send_invite_to_chatroom(to_jid, from_jid, invite_jid, invite_by_chat, send_my_data, reason)

        self.destroy()

    def popup(self):
        vb = self.get_children()[0].get_children()[0]
        vb.grab_focus()
        self.show_all()



class ChatEditDialog(Gtk.Dialog):

    def __init__(self, chat_control, plugin, default_avatar):
        self.default_avatar = default_avatar
        self.plugin = plugin
        self.chat_control = chat_control
        self.room = app.get_jid_without_resource(chat_control.room_jid)
        self.room_data = plugin.room_data[self.room]
        self.myjid = chat_control.cli_jid

        # add dialog to controls, its needed to update window data
        self.plugin.chat_edit_dialog_windows[self.room] = self
        self.plugin.send_ask_for_rights(self.myjid, self.room, type='GCMembersList', mydata=False)
        self.plugin.send_ask_for_blocks_invites(self.myjid, self.room, type='GCBlockedList')
        self.plugin.send_ask_for_blocks_invites(self.myjid, self.room, type='GCInvitedList')

        Gtk.Dialog.__init__(self, self.room_data['name'], None, 0)
        self.connect('delete_event', self.on_close)
        self.set_default_size(600, 400)

        self.main_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        self.main_box.set_margin_top(20)
        self.main_box.set_margin_bottom(20)
        self.users_notebook = Gtk.Notebook()

        css = '''#notebook{
        border: none;
        }'''
        gtkgui_helpers.add_css_to_widget(self.main_box, css)
        self.main_box.set_name('notebook')
        gtkgui_helpers.add_css_to_widget(self.users_notebook, css)
        self.users_notebook.set_name('notebook')

        self.chat_edit = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.users_members = Gtk.ScrolledWindow()
        self.users_invited = Gtk.ScrolledWindow()
        self.users_blocked = Gtk.ScrolledWindow()

        # ============================ chat editor ============================ #

        def addrow(icon_name, big_text, small_text):
            file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'icons')
            file = os.path.join(file, icon_name)
            pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(file, 24, 24, False)
            image = Gtk.Image.new_from_pixbuf(pixbuf)
            image_box = Gtk.Box()
            image_box.set_margin_right(10)
            image_box.add(image)

            row = Gtk.ListBoxRow()
            row.set_margin_top(6)
            row.set_margin_bottom(6)
            row.set_margin_left(10)
            row.set_margin_right(10)
            hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
            row.add(hbox)
            vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
            hbox.pack_start(image_box, False, False, 0)
            hbox.pack_start(vbox, True, True, 0)
            label1 = Gtk.Label(big_text, xalign=0)
            gtkgui_helpers.add_css_to_widget(label1, '#label1 { font-size: 14px; color: #616161;}')
            label1.set_name('label1')
            label2 = Gtk.Label(small_text, xalign=0)
            gtkgui_helpers.add_css_to_widget(label2, '#label2 { font-size: 12px; color: #9E9E9E;}')
            label2.set_name('label2')
            vbox.pack_start(label1, True, True, 0)
            vbox.pack_start(label2, True, True, 0)

            return row

        # top label
        self.chat_edit_listbox = Gtk.ListBox()
        self.chat_edit_listbox.set_selection_mode(Gtk.SelectionMode.NONE)
        chat_edit_label = Gtk.Label(_('Chat properties'))
        chat_edit_label.set_size_request(-1, 26)
        chat_edit_label.set_justify(Gtk.Justification.LEFT)
        chat_edit_label.set_halign(Gtk.Align.START)
        chat_edit_label.set_margin_left(10)
        self.chat_edit.pack_start(chat_edit_label, False, True, 0)
        self.chat_edit.pack_start(self.chat_edit_listbox, True, True, 0)

        # all gc data
        row = addrow('xmpp.svg', self.room, 'Jabber ID')
        self.chat_edit_listbox.add(row)
        row = addrow('account-box-outline.svg', self.room_data['name'], 'Name')
        self.chat_edit_listbox.add(row)
        row = addrow('file-document-box.svg', self.room_data['description'], 'Description')
        self.chat_edit_listbox.add(row)
        row = addrow('magnify.svg', self.room_data['searchable'], 'Indexed')
        self.chat_edit_listbox.add(row)
        row = addrow('comment-question-outline.svg', self.room_data['anonymous'], 'Anonymous')
        self.chat_edit_listbox.add(row)
        row = addrow('lock-open-outline.svg', self.room_data['model'], 'Membership')
        self.chat_edit_listbox.add(row)

        # ============================ users edit  ============================ #
        # members users list
        self.users_members_listbox = Gtk.ListBox()
        self.users_members_listbox.set_selection_mode(Gtk.SelectionMode.NONE)
        self.users_members.add(self.users_members_listbox)
        self.users_members_listbox.add(Gtk.Label(_('LOADING...')))

        # invited users list
        self.users_invited_listbox = Gtk.ListBox()
        self.users_invited_listbox.set_selection_mode(Gtk.SelectionMode.NONE)
        self.users_invited.add(self.users_invited_listbox)
        self.users_invited_listbox.add(Gtk.Label(_('LOADING...')))

        # blocked users list
        self.users_blocked_listbox = Gtk.ListBox()
        self.users_blocked_listbox.set_selection_mode(Gtk.SelectionMode.NONE)
        self.users_blocked.add(self.users_blocked_listbox)
        self.users_blocked_listbox.add(Gtk.Label(_('LOADING...')))

        scrolled = Gtk.ScrolledWindow()
        scrolled.add(self.users_members)
        self.users_notebook.append_page(scrolled, Gtk.Label(_('Chat users')))

        scrolled = Gtk.ScrolledWindow()
        scrolled.add(self.users_invited)
        self.users_notebook.append_page(scrolled, Gtk.Label(_('invited')))

        scrolled = Gtk.ScrolledWindow()
        scrolled.add(self.users_blocked)
        self.users_notebook.append_page(scrolled, Gtk.Label(_('blocked')))

        self.main_box.pack_start(self.users_notebook, True, True, 0)
        scrolled = Gtk.ScrolledWindow()
        scrolled.add(self.chat_edit)
        scrolled.set_size_request(150, -1)
        self.main_box.pack_start(scrolled, True, True, 0)

        box = self.get_content_area()
        box.pack_start(self.main_box, True, True, 0)

    def update_invited_list(self, invited=None, error=None):
        # delete old children
        children = self.users_invited_listbox.get_children()
        for child in children:
            child.destroy()

        if invited:
            for user in invited:
                file = self.default_avatar
                pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(file, 32, 32, False)
                av_image = Gtk.Image.new_from_pixbuf(pixbuf)
                avatar_event_box = Gtk.EventBox()
                avatar_event_box.add(av_image)
                avatar_event_box.set_margin_right(8)
                avatar_event_box.set_margin_left(8)

                user_jid = Gtk.Label(user)
                user_jid.set_justify(Gtk.Justification.LEFT)
                user_jid.set_halign(Gtk.Align.START)
                user_jid.set_ellipsize(Pango.EllipsizeMode.END)
                gtkgui_helpers.add_css_to_widget(user_jid, '#user_jid { font-size: 14px; color: #000000;}')
                user_jid.set_name('user_jid')
                user_jid.set_margin_right(8)
                user_jid_grid = Gtk.Grid()
                user_jid_grid.add(user_jid)

                file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'icons')
                file = os.path.join(file, 'undo.svg')
                pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(file, 24, 24, True)
                image = Gtk.Image.new_from_pixbuf(pixbuf)
                undo = Gtk.EventBox()
                undo.connect('button-press-event', self.on_send_revoke, user)
                undo.add(image)

                hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
                hbox.pack_start(avatar_event_box, False, True, 0)
                hbox.pack_start(user_jid_grid, True, True, 0)
                hbox.pack_start(undo, False, True, 0)

                av_image.show()
                avatar_event_box.show()
                image.show()
                user_jid.show()
                user_jid_grid.show()
                undo.show()
                hbox.show()
                hbox.set_margin_right(8)
                hbox.set_margin_left(8)
                hbox.set_margin_top(4)
                hbox.set_margin_bottom(4)
                self.users_invited_listbox.add(hbox)

            if not len(invited):
                empty = Gtk.Label(_('List is empty'))
                empty.show()
                self.users_invited_listbox.add(empty)

        if error:
            empty = Gtk.Label(error)
            empty.show()
            self.users_invited_listbox.add(empty)

        self.users_invited_listbox.show()

    def update_blocked_list(self, blocked):
        # delete old children
        children = self.users_blocked_listbox.get_children()
        for child in children:
            child.destroy()

        for user in blocked:
            file = self.default_avatar
            pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(file, 32, 32, False)
            av_image = Gtk.Image.new_from_pixbuf(pixbuf)
            avatar_event_box = Gtk.EventBox()
            avatar_event_box.add(av_image)
            avatar_event_box.set_margin_right(8)
            avatar_event_box.set_margin_left(8)

            user_id = user['id']

            user_jid = Gtk.Label(user['jid'])
            user_jid.set_justify(Gtk.Justification.LEFT)
            user_jid.set_halign(Gtk.Align.START)
            user_jid.set_ellipsize(Pango.EllipsizeMode.END)
            gtkgui_helpers.add_css_to_widget(user_jid, '#user_jid { font-size: 14px; color: #000000;}')
            user_jid.set_name('user_jid')
            user_jid.set_margin_right(8)
            user_jid_grid = Gtk.Grid()
            user_jid_grid.add(user_jid)

            file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'icons')
            file = os.path.join(file, 'block-helper.svg')
            pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(file, 24, 24, True)
            image = Gtk.Image.new_from_pixbuf(pixbuf)
            undo = Gtk.EventBox()
            undo.connect('button-press-event', self.on_send_unblock, user_id)
            undo.add(image)

            hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
            hbox.pack_start(avatar_event_box, False, True, 0)
            hbox.pack_start(user_jid_grid, True, True, 0)
            hbox.pack_start(undo, False, True, 0)

            av_image.show()
            avatar_event_box.show()
            image.show()
            user_jid.show()
            user_jid_grid.show()
            undo.show()
            hbox.show()
            hbox.set_margin_right(8)
            hbox.set_margin_left(8)
            hbox.set_margin_top(4)
            hbox.set_margin_bottom(4)
            self.users_blocked_listbox.add(hbox)

        if len(blocked) == 0:
            empty = Gtk.Label(_('List is empty'))
            empty.show()
            self.users_blocked_listbox.add(empty)

        self.users_blocked_listbox.show()


    def update_members_list(self, users, AVATARS_DIR):
        # delete old children
        children = self.users_members_listbox.get_children()
        for child in children:
            child.destroy()

        # create new children
        for user in users:
            user_event_box = Gtk.EventBox()
            user_event_box.connect('button-press-event', self.on_user_click, user['id'])
            hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
            user_event_box.add(hbox)
            hbox.set_margin_top(4)
            hbox.set_margin_bottom(4)
            vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
            # avatar
            try:
                path = os.path.normpath(AVATARS_DIR + '/' + user['av_id'] + '.jpg')
                file = open(path)
                file = os.path.normpath(path)
            except:
                file = self.default_avatar

            pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(file, 32, 32, False)
            image = Gtk.Image.new_from_pixbuf(pixbuf)
            avatar_event_box = Gtk.EventBox()
            avatar_event_box.add(image)
            avatar_event_box.set_margin_right(8)
            avatar_event_box.set_margin_left(8)

            # nickname badge jid
            nickname = Gtk.Label(user['nickname'])
            nickname.set_justify(Gtk.Justification.LEFT)
            nickname.set_halign(Gtk.Align.START)
            nickname.set_ellipsize(Pango.EllipsizeMode.END)
            badge = Gtk.Label(user['badge'])
            badge.set_justify(Gtk.Justification.LEFT)
            badge.set_halign(Gtk.Align.START)
            badge.set_ellipsize(Pango.EllipsizeMode.END)
            badge.set_margin_left(8)
            jid = Gtk.Label(user['jid'])

            gtkgui_helpers.add_css_to_widget(nickname, '#nickname { font-size: 14px; color: #000000;}')
            nickname.set_name('nickname')
            gtkgui_helpers.add_css_to_widget(badge, '#badge { font-size: 12px; color: #616161;}')
            badge.set_name('badge')
            gtkgui_helpers.add_css_to_widget(jid, '#jid { font-size: 12px; color: #9E9E9E;}')
            jid.set_name('jid')
            jid.set_justify(Gtk.Justification.LEFT)
            jid.set_halign(Gtk.Align.START)

            nick_badge_grid = Gtk.Grid()
            nick_badge_grid.attach(nickname, 0, 0, 1, 1)
            nick_badge_grid.attach(badge, 1, 0, 1, 1)
            vbox.pack_start(nick_badge_grid, False, True, 0)
            vbox.pack_start(jid, False, True, 0)

            # usertype
            icons_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'icons')
            if user['usertype'] == 'admin':
                file = os.path.join(icons_path, 'star-outline.svg')
            elif user['usertype'] == 'owner':
                file = os.path.join(icons_path, 'star.svg')
            else:
                file = None

            hbox.pack_start(avatar_event_box, False, True, 0)
            hbox.pack_start(vbox, True, True, 0)

            # TODO usertypes

            star_image = None
            image_box = None
            print(file)
            print(user['usertype'])
            if file:
                pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(file, 16, 16, False)
                star_image = Gtk.Image.new_from_pixbuf(pixbuf)
                image_box = Gtk.Box()
                image_box.add(star_image)
                image_box.set_margin_right(8)
                image_box.set_margin_left(8)
                hbox.pack_start(image_box, False, True, 0)

            self.users_members_listbox.add(user_event_box)
            user_event_box.show()
            image.show()
            avatar_event_box.show()
            hbox.show()
            vbox.show()
            nickname.show()
            badge.show()
            jid.show()
            nick_badge_grid.show()
            if file:
                star_image.show()
                image_box.show()

        self.users_members_listbox.show()

    def on_send_revoke(self, eb, event, jid):
        print(jid)
        self.plugin.send_unblock_or_revoke(self.myjid, room=self.room, jid_id=jid, revoke=True)

    def on_send_unblock(self, eb, event, id):
        print(id)
        self.plugin.send_unblock_or_revoke(self.myjid, room=self.room, jid_id=id, unblock=True)

    def on_user_click(self, eb, event, u_id):
        self.plugin.send_ask_for_rights(self.myjid, room=self.room, id=u_id, type='XGCUserOptions')

    def on_close(self, eb=None, event=None):
        del self.plugin.chat_edit_dialog_windows[self.room]

    def popup(self):
        vb = self.get_children()[0].get_children()[0]
        vb.grab_focus()
        self.show_all()



class ChoseSendForwardTo(Gtk.Dialog):

    def __init__(self, chat_control, plugin, default_avatar, messages):
        gajimpaths = configpaths.gajimpaths
        self.AVATAR_PATH = gajimpaths['AVATAR']
        self.chat_control = chat_control
        self.plugin = plugin
        self.default_avatar = default_avatar
        self.chosen_messages_data = messages
        self.CHOOSED_USER = None
        self.user_widgets = []

        Gtk.Dialog.__init__(self, _('Forward'), None, 0)
        self.set_default_size(400, 600)

        self.search = Gtk.Entry()
        self.search.set_icon_from_icon_name(Gtk.EntryIconPosition.PRIMARY, 'system-search-symbolic')
        self.search.set_placeholder_text(_('Search'))
        self.search.set_margin_left(20)
        self.search.set_margin_right(20)
        self.search.set_margin_top(20)

        # ============================== scroll window ============================== #
        scrolled = Gtk.ScrolledWindow()
        listbox = Gtk.ListBox()
        listbox.set_selection_mode(Gtk.SelectionMode.NONE)
        scrolled.add(listbox)
        scrolled.set_margin_left(20)
        scrolled.set_margin_right(20)
        scrolled.set_margin_top(20)
        scrolled.set_margin_bottom(20)

        user_list = []

        account = None
        accounts = app.contacts.get_accounts()
        for acc in accounts:
            realjid = app.get_jid_from_account(acc)
            realjid = app.get_jid_without_resource(str(realjid))
            if self.chat_control.cli_jid == realjid:
                account = acc

        jids = app.contacts.get_contacts_jid_list(account)
        for jid in jids:
            jid = app.get_jid_without_resource(str(jid))
            contact = app.contacts.get_contact_with_highest_priority(account, jid)
            name = contact.get_shown_name()
            if not name:
                name = jid
            if (name, jid) not in user_list:
                avatar_sha = app.contacts.get_avatar_sha(account, jid)
                user_list.append((name, jid, avatar_sha))


        for data in user_list:
            data_name = data[0]
            data_jid = data[1]
            avatar_sha = data[2]

            if avatar_sha:
                path = os.path.join(self.AVATAR_PATH, avatar_sha)
                pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(path, 32, 32, False)
                # pixbuf = Gdk.pixbuf_get_from_surface(pixbuf, 0, 0, 32, 32)
            else:
                pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(self.default_avatar, 32, 32, False)
            image = Gtk.Image.new_from_pixbuf(pixbuf)
            css = '''
                #xavatar {}

                #user_jid{
                background: none;
                font-size: 11px;
                color: #9E9E9E;
                }
                #user_name{
                color: #212121;
                font-size: 16px;
                background: none;
                }
                '''
            gtkgui_helpers.add_css_to_widget(image, css)
            image.set_name('xavatar')

            name = Gtk.TextView()
            name.get_buffer().set_text(data_name)
            name.set_editable(False)
            gtkgui_helpers.add_css_to_widget(name, css)
            name.set_name('user_name')

            jid = Gtk.TextView()
            jid.get_buffer().set_text(data_jid)
            jid.set_editable(False)
            gtkgui_helpers.add_css_to_widget(jid, css)
            jid.set_name('user_jid')

            vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
            vbox.pack_start(name, False, True, 0)
            vbox.pack_start(jid, False, True, 0)

            hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=50)
            hbox.pack_start(image, False, False, 0)
            hbox.pack_start(vbox, False, False, 0)
            hbox.set_margin_top(4)
            hbox.set_margin_bottom(4)

            eventbox = Gtk.EventBox()
            eventbox.connect('button-press-event', self.on_user_clicked, eventbox, data_jid)
            eventbox.add(hbox)
            name.show()
            jid.show()
            vbox.show()
            eventbox.show()

            listbox.add(eventbox)
            self.user_widgets.append((eventbox, data_name, data_jid))

        css = '''
                            #Xbutton-redfont {
                            color: #D32F2F;
                            margin: 0 5px;
                            padding: 0 10px;
                            background-color: #FFFFFF;
                            background: #FFFFFF;
                            border: none;
                            border-radius: 2px;
                            font-size: 13px;
                            font-weight: bold;
                            }
                            #Xbutton-redfont:hover{
                            background-color: #E0E0E0;
                            background: #E0E0E0;
                            }
                            '''
        btn_fwd = Gtk.Button(_('Forward'))
        btn_fwd.connect('button-press-event', self.on_forward_clicked)
        gtkgui_helpers.add_css_to_widget(btn_fwd, css)
        btn_fwd.set_name('Xbutton-redfont')
        leftgrid = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        rightgrid = Gtk.Box()
        leftgrid.pack_start(Gtk.Label(''), True, True, 0)
        rightgrid.pack_start(btn_fwd, False, True, 0)

        button_hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        button_hbox.set_margin_bottom(10)
        button_hbox.set_margin_left(20)
        button_hbox.set_margin_right(20)
        button_hbox.set_size_request(-1, 36)

        button_hbox.pack_start(leftgrid, True, True, 0)
        button_hbox.pack_start(rightgrid, False, True, 0)

        box = self.get_content_area()
        box.pack_start(self.search, False, True, 0)
        box.pack_start(scrolled, True, True, 0)
        box.pack_start(button_hbox, False, True, 0)

        self.search.connect("changed", self.edit_changed)

    def on_forward_clicked(self, eb, event):
        print('forward')
        print(self.CHOOSED_USER)

        # self, additional_data, tojid, myjid, room, body
        for message in self.chosen_messages_data:
            if message[1]['forward']:
                self.plugin.send_forward_message(message[1]['forward'],
                                                 self.CHOOSED_USER,
                                                 self.chat_control.cli_jid,
                                                 self.chat_control.room_jid,
                                                 '>' + message[3] + '\n>' + message[4])
            else:
                self.plugin.send_forward_message(message[1],
                                                 self.CHOOSED_USER,
                                                 self.chat_control.cli_jid,
                                                 self.chat_control.room_jid,
                                                 '>' + message[3] + '\n>' + message[4])

        self.chat_control.remove_message_selection()
        self.destroy()

    def edit_changed(self, widget):
        s = self.search.get_text()
        for widget in self.user_widgets:
            if s.lower() in widget[1].lower() or s.lower() in widget[2].lower():
                widget[0].show()
            else:
                widget[0].hide()

    def on_user_clicked(self, eb, event, widget, jid):
        css = '''
        #choosed {
        background-color: #FFCCCC;
        }
        #nonchoosed {}
        '''
        # left click
        if event.type == Gdk.EventType.BUTTON_PRESS and event.button == 1:
            if jid == self.CHOOSED_USER:
                gtkgui_helpers.add_css_to_widget(widget, css)
                widget.set_name('nonchoosed')
                self.CHOOSED_USER = None
            else:
                for wid in self.user_widgets:
                    wid = wid[0]
                    gtkgui_helpers.add_css_to_widget(wid, css)
                    wid.set_name('nonchoosed')
                gtkgui_helpers.add_css_to_widget(widget, css)
                widget.set_name('choosed')
                self.CHOOSED_USER = jid

    def popup(self):
        vb = self.get_children()[0].get_children()[0]
        vb.grab_focus()
        self.show_all()


