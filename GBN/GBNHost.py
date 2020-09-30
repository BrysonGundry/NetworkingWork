from Simulator import Simulator, Packet, EventEntity
from enum import Enum
from struct import pack, unpack
# Bryson Gundry
# 11/26/2019
# GBN Project

# Additionally, you will need to write code to pack/unpack data into a byte representation appropriate for 
# communication across a network. For this assignment, you will assume that all packets use the following header:
# - Sequence Number (int)           -- Set to 0 if this is an ACK
# - Acknowledgement Number (int)    -- Set to 0 if this is not an ACK
# - Checksum (half)                 -- Compute the Internet Checksum, as discussed in class
# - Acknowledgement Flag (boolean)  -- Set to True if sending an ACK, otherwise False
# - Payload length, in bytes (int)  -- Set this to 0 when sending an ACK message, as these will not carry a payload
# - Payload (string)                -- Leave this empty when sending an ACK message
# When unpacking data in this format, it is recommended to first unpack the fixed length header. After unpacking the
# header, you can determine if there is a payload, based on the size of Payload Length.
# NOTE: It is possible for payload length to be corrupted. In this case, you will get an Exception similar to
#       "unpack requires a buffer of ##### bytes". If you receive this exception, this is a sign that the packet is
#       corrupt. This is not the only way the packet can be corrupted, but is a special case of corruption that will
#       prevent you from unpacking the payload. If you can unpack the payload, use the checksum to determine if the
#       packet is corrupted. If you CAN'T unpack the payload, then you already KNOW that the packet is corrupted.
# When unpacking a packet, you can store the values in the Packet class, defined in the constructor. You MUST send 
# data between hosts in a byte representation, but after receiving a packet you may find it convenient to
# store the values in this class, as it will allow you to refer to them by name in your code, rather than via
# the array indicies produced by unpack(). 
class GBNHost:
    def __init__(self, simulator, entity, timer_interval, window_size):
        # These are important state values that you will need to use in your code
        self.simulator = simulator
        self.entity = entity
        # Sender properties
        self.timer_interval = timer_interval  # The duration the timer lasts before triggering
        self.window_size = window_size  # The size of the seq/ack window
        self.last_ACKed = 0  # The last ACKed packet. This starts at 0 because no packets
        # have been ACKed
        self.current_seq_number = 1  # The SEQ number that will be used next
        self.app_layer_buffer = []  # A buffer that stores all data received from the application
        # layer that hasn't yet been sent
        self.unACKed_buffer = {}  # A buffer that stores all sent but unACKed packets
        # Receiver properties
        self.expected_seq_number = 1  # The next SEQ number expected
        self.last_ACK_pkt = self.create_packet(0, 0, None, True)  # The last ACK pkt sent.
        # TODO: This should be initialized to an ACK response with an
        #       ACK number of 0. If a problem occurs with the first
        #       packet that is received, then this default ACK should
        #       be sent in response, as no real packet has been rcvd yet

    ###########################################################################################################
    def checksum(self, pkt):
        # checking odd length
        if len(pkt) % 2 == 1:
            pkt += b'\x00'
        checksum = 0

        for i in range(0, len(pkt), 2):
            w = pkt[i] << 8 | pkt[i + 1]
            checksum += w
            checksum = (checksum & 0xffff) + (checksum >> 16)
        return ~checksum & 0xffff

    def create_packet(self, sequence_num, ack, payload, is_ack):   
        if payload == None:
            pkt = pack("!ii?i", 0, ack, True, 0)
            checksum = self.checksum(pkt)
            pkt = pack("!iiH?i", 0, ack, checksum, True, 0)  
            return pkt
    
        else:
            pkt = pack('!ii?i%is'%len(payload), sequence_num, 0, False, len(payload), payload.encode())
            checksum = self.checksum(pkt)
            pkt = pack('!iiH?i%is'%len(payload), sequence_num, 0, checksum, False, len(payload), payload.encode())  
            return pkt

    def receive_from_application_layer(self, payload):
        if self.current_seq_number < (self.last_ACKed + 1) + self.window_size:
            self.unACKed_buffer[self.current_seq_number] = self.create_packet(self.current_seq_number, 0, payload,
                                                                              False)
            self.simulator.to_layer3(self.entity, self.unACKed_buffer[self.current_seq_number], False)
            if self.last_ACKed + 1 == self.current_seq_number:
                self.simulator.start_timer(self.entity, self.timer_interval)
            self.current_seq_number += 1
        else:
            self.app_layer_buffer.append(self.create_packet(self.current_seq_number, 0, payload, False))

    #if data is not corrupt
    def not_corrupt(self, rcvpkt, pkt):
        return rcvpkt[2] == pkt

    @staticmethod
    def has_seq_num(rcvpkt, expectedseqnum):
        return rcvpkt[0] == expectedseqnum

    def receive_from_network_layer(self, byte_data):
        header = unpack("!iiH?i", byte_data[:15])
        iscorruption = False
        length = header[4]  

        try:
            if length > 0:
                payload = unpack("%is" % length, byte_data[15:])[0].decode()
            else:
                payload = None
        except Exception as e:
            iscorruption = True

        # Processing Data
        if iscorruption == False and not header[3] and self.expected_seq_number == header[0]:
            self.simulator.to_layer5(self.entity, payload)
            snd_pkt = self.create_packet(0, self.expected_seq_number, None, True)
            self.simulator.to_layer3(self.entity, snd_pkt, True)
            self.last_ACK_pkt = snd_pkt
            self.expected_seq_number += 1
    
        if iscorruption == False and header[3]:
            self.last_ACKed = header[1]
            base = self.last_ACKed + 1
            if base == self.current_seq_number:
                self.simulator.stop_timer(self.entity)
            else:
                self.simulator.to_layer3(self.entity, self.last_ACK_pkt, True)
        else:
            self.simulator.to_layer3(self.entity, self.last_ACK_pkt, True)

    def timer_interrupt(self):
        self.simulator.start_timer(self.entity, self.timer_interval)
        for seq_num in self.unACKed_buffer:
            self.simulator.to_layer3(self.entity, self.unACKed_buffer[seq_num], False)
