#ifndef NET_COMMON_H
#define NET_COMMON_H

#include <stdint.h>

struct eth_hdr {
    uint8_t dst[6];
    uint8_t src[6];
    uint16_t ethertype;
} __attribute__((packed));

struct arp_hdr {
    uint16_t htype;
    uint16_t ptype;
    uint8_t hlen;
    uint8_t plen;
    uint16_t op;
    uint8_t sha[6];
    uint32_t spa;
    uint8_t tha[6];
    uint32_t tpa;
} __attribute__((packed));

int iface_index(int fd, const char *iface);
int get_iface_mac(int fd, const char *iface, uint8_t *mac);
int get_iface_ipv4(int fd, const char *iface, uint32_t *ip);
int get_iface_netmask(int fd, const char *iface, uint32_t *mask);
int open_raw_socket(int fd_hint, const char *iface);

#endif
