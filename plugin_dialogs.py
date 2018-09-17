import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk
from gajim import gtkgui_helpers

class UserDataDialog(Gtk.Dialog):

    def __init__(self, plugin, userdata, image, chat_control):


        nickname_text = userdata['nickname']
        badge_text = userdata['badge']
        if userdata['jid'] == 'Unknown':
            user_id = userdata['id']
        else: user_id = userdata['jid']

        Gtk.Dialog.__init__(self, nickname_text, None, 0)
        self.add_button('save', 1)

        self.set_default_size(480, 480)

        header_grid = Gtk.Grid()
        avatar = Gtk.EventBox()
        avatar.connect('button-press-event', chat_control.on_upload_avatar_dialog, userdata)
        avatar.add(image)
        avatar.set_margin_left(20)
        avatar.set_margin_right(20)
        avatar.set_margin_top(10)
        avatar.set_margin_bottom(10)
        avatar.set_size_request(40, 40)

        nickname = Gtk.TextView()
        nickname.get_buffer().set_text(nickname_text)
        nickname.set_margin_top(10)

        badge = Gtk.TextView()
        badge.get_buffer().set_text(badge_text)
        badge.set_margin_left(10)
        badge.set_margin_top(10)
        badge.set_margin_right(20)

        namebadge_grid = Gtk.Grid()
        namebadge_grid.attach(nickname, 0, 0, 1, 1)
        namebadge_grid.attach(badge, 1, 0, 1, 1)

        jid_id = Gtk.TextView()
        jid_id.get_buffer().set_text(user_id)
        jid_id.set_margin_bottom(10)
        jid_id_grid = Gtk.Grid()
        jid_id_grid.add(jid_id)

        header_grid.attach(avatar, 0, 0, 1, 2)
        header_grid.attach(namebadge_grid, 1, 0, 1, 1)
        header_grid.attach(jid_id_grid, 1, 1, 1, 1)

        # rights listbox
        # scrolled = Gtk.ScrolledWindow()
        # scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        # scrolled.set_size_request(-1, 400)
        listbox = Gtk.ListBox()
        listbox.set_selection_mode(Gtk.SelectionMode.NONE)
        # scrolled.add(listbox)

        def addrow(name, state, expires='Not able'):

            text = name
            row = Gtk.ListBoxRow()
            hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=50)
            hbox.set_margin_left(20)
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
            switch.set_margin_right(20)
            hbox.pack_start(switch, False, True, 0)
            return row

        # welcome to india, lets dance!
        # India ens, sorry but that was fun :)
        listbox.add(Gtk.Label('Restrictions'))
        res = userdata['rights']['restrictions']

        for i in ['read', 'send-audio', 'send-image', 'write']:
            if i in res:
                listbox.add(addrow(i, True, res[i][0]))
            else:
                listbox.add(addrow(i, False))

        listbox.add(Gtk.Label('Permissions'))
        res = userdata['rights']['permissions']

        for i in ['owner', 'block-member', 'change-badge', 'change-chat',
                'change-nickname', 'change-restriction', 'invite-member', 'remove-member']:
            if i in res:
                listbox.add(addrow(i, True, res[i][0]))
            else:
                listbox.add(addrow(i, False))



        box = self.get_content_area()
        css = '''#box_content_area {
        background-color: #FFFFFF;}'''
        gtkgui_helpers.add_css_to_widget(box, css)
        box.set_name('box_content_area')
        print(type(box))
        box.add(header_grid)
        box.add(listbox)
        self.show_all()

    def popup(self):
        vb = self.get_children()[0].get_children()[0]
        vb.grab_focus()
        self.show_all()


