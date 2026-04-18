from ryu.base import app_manager
from ryu.topology import event
from ryu.topology.api import get_switch, get_link
from ryu.controller.handler import set_ev_cls
from ryu.controller.handler import MAIN_DISPATCHER

class TopologyDetector(app_manager.RyuApp):

    def __init__(self, *args, **kwargs):
        super(TopologyDetector, self).__init__(*args, **kwargs)
        self.topology = {'switches': [], 'links': []}

    # Detect switch enter
    @set_ev_cls(event.EventSwitchEnter)
    def switch_enter_handler(self, ev):
        self.logger.info("Switch Added")
        self.update_topology()

    # Detect switch leave
    @set_ev_cls(event.EventSwitchLeave)
    def switch_leave_handler(self, ev):
        self.logger.info("Switch Removed")
        self.update_topology()

    # Detect link add
    @set_ev_cls(event.EventLinkAdd)
    def link_add_handler(self, ev):
        self.logger.info("Link Added")
        self.update_topology()

    # Detect link delete
    @set_ev_cls(event.EventLinkDelete)
    def link_delete_handler(self, ev):
        self.logger.info("Link Removed")
        self.update_topology()

    def update_topology(self):
        switch_list = get_switch(self, None)
        link_list = get_link(self, None)

        switches = [sw.dp.id for sw in switch_list]
        links = [(l.src.dpid, l.dst.dpid) for l in link_list]

        self.topology['switches'] = switches
        self.topology['links'] = links

        self.logger.info("Updated Topology:")
        self.logger.info("Switches: %s", switches)
        self.logger.info("Links: %s", links)