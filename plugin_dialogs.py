import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk
from gajim import gtkgui_helpers
from gajim.common import app

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



