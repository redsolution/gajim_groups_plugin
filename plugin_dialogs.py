import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk
from gajim import gtkgui_helpers

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

        if 'owner' in self.self_userdata['rights']['permissions']:
            self.is_owner = True
        if 'remove-member' in self.self_userdata['rights']['permissions']:
            self.can_kick = False
        if 'block-member' in self.self_userdata['rights']['permissions']:
            self.can_block = True
        a = ['change-badge', 'change-nickname', 'change-restriction']
        if list(set(a) & set(self.self_userdata['rights']['permissions'])):
            self.can_edit = True


        self.set_default_size(480, 480)
        self.rights = {}
        self.switches = {}

        # =========================== header ============================= #
        css = '''
        #edit_allow{
        border: none;
        border-bottom: 1px dotted black;
        background: #CCCCCC;
        padding-left: 5px;
        padding-right: 5px;
        }
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

        self.nickname = Gtk.TextView()
        self.nickname.get_buffer().set_text(nickname_text)
        self.nickname.set_margin_top(10)
        self.nickname.set_size_request(48, -1)

        if 'change-nickname' in self.self_userdata['rights']['permissions'] or self.is_owner:
            gtkgui_helpers.add_css_to_widget(self.nickname, css)
            self.nickname.set_name('edit_allow')
            self.nickname.set_editable(True)
        else:
            self.nickname.set_editable(False)

        self.badge = Gtk.TextView()
        self.badge.get_buffer().set_text(badge_text)
        self.badge.set_margin_left(10)
        self.badge.set_margin_top(10)
        self.badge.set_margin_right(20)
        self.badge.set_size_request(48, -1)

        if 'change-badge' in self.self_userdata['rights']['permissions'] or self.is_owner:
            gtkgui_helpers.add_css_to_widget(self.badge, css)
            self.badge.set_name('edit_allow')
            self.badge.set_editable(True)
        else:
            self.badge.set_editable(False)

        namebadge_grid = Gtk.Grid()
        namebadge_grid.attach(self.nickname, 0, 0, 1, 1)
        namebadge_grid.attach(self.badge, 1, 0, 1, 1)

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
        listbox = Gtk.ListBox()
        listbox.set_selection_mode(Gtk.SelectionMode.NONE)
        # scrolled.add(listbox)

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
                listbox.add(addrow(i, True, res[i][0]))
            else:
                listbox.add(addrow(i, False))

        PermLabel = Gtk.Label('Permissions')
        PermLabel.set_margin_bottom(10)
        PermLabel.set_margin_top(10)
        listbox.add(PermLabel)
        res = userdata['rights']['permissions']

        for i in ['owner', 'block-member', 'change-badge', 'change-chat',
                'change-nickname', 'change-restriction', 'invite-member', 'remove-member']:
            if i in res:
                listbox.add(addrow(i, True, res[i][0]))
            else:
                listbox.add(addrow(i, False))
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

        btn_kick = Gtk.Button(_('kick'))
        btn_block = Gtk.Button(_('block'))
        btn_save = Gtk.Button(_('save'))
        btn_save.connect('button-press-event', self.on_save_clicked)
        btn_kick.set_size_request(64, 36)
        btn_kick.set_margin_right(10)
        btn_block.set_size_request(64, 36)
        btn_save.set_size_request(64, 36)

        gtkgui_helpers.add_css_to_widget(btn_kick, css)
        btn_kick.set_name('Xbutton-blackfont')
        gtkgui_helpers.add_css_to_widget(btn_block, css)
        btn_block.set_name('Xbutton-blackfont')
        gtkgui_helpers.add_css_to_widget(btn_save, css)
        btn_save.set_name('Xbutton-redfont')



        if self.can_edit or self.is_owner:
            rightgrid.pack_start(btn_save, False, True, 0)
        if self.can_kick or self.is_owner:
            leftgrid.pack_start(btn_kick, False, True, 0)
        if self.can_block or self.is_owner:
            leftgrid.pack_start(btn_block, False, True, 0)

        # =========================== end buttons at the bottom ============================= #

        box = self.get_content_area()
        css = '''#box_content_area {
        background-color: #FFFFFF;}'''
        gtkgui_helpers.add_css_to_widget(box, css)
        box.set_name('box_content_area')
        print(type(box))
        box.add(header_grid)
        box.add(listbox)
        box.add(button_hbox)
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
        self.destroy()
        # =========================== end if rights changed =========================== #

    def popup(self):
        vb = self.get_children()[0].get_children()[0]
        vb.grab_focus()
        self.show_all()


