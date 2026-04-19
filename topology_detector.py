from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import CONFIG_DISPATCHER, MAIN_DISPATCHER
from ryu.controller.handler import set_ev_cls
from ryu.ofproto import ofproto_v1_3
from ryu.lib.packet import packet, ethernet, ether_types
from ryu.topology import event as topo_event
from ryu.topology.api import get_switch, get_link
import logging

LOG = logging.getLogger('topology_detector')


class TopologyChangeDetector(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super(TopologyChangeDetector, self).__init__(*args, **kwargs)
        self.topology_api_app = self
        self.switches = {}
        self.links = {}
        self.mac_to_port = {}
        LOG.info("=== Topology Change Detector Started ===")

    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features_handler(self, ev):
        datapath = ev.msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        match = parser.OFPMatch()
        actions = [parser.OFPActionOutput(ofproto.OFPP_CONTROLLER,
                                          ofproto.OFPCML_NO_BUFFER)]
        self.add_flow(datapath, 0, match, actions)

    def add_flow(self, datapath, priority, match, actions, buffer_id=None):
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        inst = [parser.OFPInstructionActions(ofproto.OFPIT_APPLY_ACTIONS, actions)]
        if buffer_id:
            mod = parser.OFPFlowMod(datapath=datapath, buffer_id=buffer_id,
                                    priority=priority, match=match, instructions=inst)
        else:
            mod = parser.OFPFlowMod(datapath=datapath, priority=priority,
                                    match=match, instructions=inst)
        datapath.send_msg(mod)

    @set_ev_cls(topo_event.EventSwitchEnter)
    def switch_enter_handler(self, ev):
        switch = ev.switch
        dpid = switch.dp.id
        self.switches[dpid] = switch
        LOG.info("[TOPOLOGY] Switch ADDED:   dpid=%d  ports=%d", dpid, len(switch.ports))
        self._print_topology()

    @set_ev_cls(topo_event.EventSwitchLeave)
    def switch_leave_handler(self, ev):
        switch = ev.switch
        dpid = switch.dp.id
        self.switches.pop(dpid, None)
        LOG.info("[TOPOLOGY] Switch REMOVED: dpid=%d", dpid)
        self._print_topology()

    @set_ev_cls(topo_event.EventLinkAdd)
    def link_add_handler(self, ev):
        link = ev.link
        src = link.src
        dst = link.dst
        key = (src.dpid, dst.dpid)
        self.links[key] = link
        LOG.info("[TOPOLOGY] Link ADDED:    %d:%s --> %d:%s",
                 src.dpid, src.port_no, dst.dpid, dst.port_no)
        self._print_topology()

    @set_ev_cls(topo_event.EventLinkDelete)
    def link_delete_handler(self, ev):
        link = ev.link
        src = link.src
        dst = link.dst
        key = (src.dpid, dst.dpid)
        self.links.pop(key, None)
        LOG.info("[TOPOLOGY] Link REMOVED:  %d:%s --> %d:%s",
                 src.dpid, src.port_no, dst.dpid, dst.port_no)
        self._print_topology()

    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def packet_in_handler(self, ev):
        msg = ev.msg
        datapath = msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        in_port = msg.match['in_port']

        pkt = packet.Packet(msg.data)
        eth = pkt.get_protocols(ethernet.ethernet)[0]

        if eth.ethertype == ether_types.ETH_TYPE_LLDP:
            return

        dst = eth.dst
        src = eth.src
        dpid = datapath.id

        self.mac_to_port.setdefault(dpid, {})
        self.mac_to_port[dpid][src] = in_port

        if dst in self.mac_to_port[dpid]:
            out_port = self.mac_to_port[dpid][dst]
        else:
            out_port = ofproto.OFPP_FLOOD

        actions = [parser.OFPActionOutput(out_port)]

        if out_port != ofproto.OFPP_FLOOD:
            match = parser.OFPMatch(in_port=in_port, eth_dst=dst)
            self.add_flow(datapath, 1, match, actions)

        data = msg.data if msg.buffer_id == ofproto.OFP_NO_BUFFER else None
        out = parser.OFPPacketOut(datapath=datapath, buffer_id=msg.buffer_id,
                                  in_port=in_port, actions=actions, data=data)
        datapath.send_msg(out)

    def _print_topology(self):
        LOG.info("--- Current Topology ---")
        LOG.info("  Switches (%d): %s", len(self.switches), list(self.switches.keys()))
        LOG.info("  Links    (%d):", len(self.links))
        for (s, d), link in self.links.items():
            LOG.info("    %d:%s --> %d:%s", s, link.src.port_no, d, link.dst.port_no)
        LOG.info("------------------------")
