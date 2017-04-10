class ActionStateHelper():
    all = []

    def __init__(self, action):
        self.action = action
        self.tooltip = action.toolTip()
        self.enabled_test = []

        ActionStateHelper.all += [self]

    def add_is_enabled_test(self, l):
        self.enabled_test += [l]
        return self

    def update_state(self):
        for test in self.enabled_test:
            enabled, tooltip = test(self.action)
            if not enabled:
                self.action.setToolTip(tooltip)
                self.action.setEnabled(False)
                return

        self.action.setToolTip(self.tooltip)
        self.action.setEnabled(True)

    @staticmethod
    def update_all():
        for h in ActionStateHelper.all:
            h.update_state()

    @staticmethod
    def remove_all():
        ActionStateHelper.all = []
