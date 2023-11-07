-- west build: running target ram_report
[0/1] cd /workspaces/concord/apps/dns-sec/build && /usr/bin/python3.10 /ncs/zephyr/scripts/footprint/size_report -k /workspaces/concord/apps/dns-sec/build/zephyr/zephyr.elf -z /ncs/zephyr -o /workspaces/concord/apps/dns-sec/build --workspace=/ncs -d 99 ram
Path                                                                                             Size    %  
==============================================================================================================
Root                                                                                            47079 100.00%
├── (hidden)                                                                                       59   0.13%
├── (no paths)                                                                                   7281  15.47%
│   ├── CCAsymCryptoMutex                                                                           4   0.01%
│   ├── CCPowerMutex                                                                                4   0.01%
│   ├── CCRndCryptoMutex                                                                            4   0.01%
│   ├── CCSymCryptoMutex                                                                            4   0.01%
│   ├── __malloc_free_list                                                                          4   0.01%
│   ├── _impure_ptr                                                                                 4   0.01%
│   ├── _kernel                                                                                    40   0.08%
│   ├── _sw_isr_table                                                                             384   0.82%
│   ├── buf.0                                                                                     440   0.93%
│   ├── cli.1                                                                                      16   0.03%
│   ├── ctx.0                                                                                     244   0.52%
│   ├── data.0                                                                                      3   0.01%
│   ├── hints.0                                                                                    80   0.17%
│   ├── impure_data                                                                                96   0.20%
│   ├── invalid_aes_256_bit_key                                                                     4   0.01%
│   ├── k_sys_work_q                                                                              216   0.46%
│   ├── mbedtls_mutex_init                                                                          4   0.01%
│   ├── mbedtls_mutex_lock                                                                          4   0.01%
│   ├── mbedtls_mutex_unlock                                                                        4   0.01%
│   ├── nrf_cc3xx_platform_ctr_drbg_global_ctx                                                    448   0.95%
│   ├── nrf_cc3xx_platform_initialized                                                              4   0.01%
│   ├── nrf_cc3xx_platform_rng_initialized                                                          4   0.01%
│   ├── on.2                                                                                        4   0.01%
│   ├── once.0                                                                                      1   0.00%
│   ├── once.1                                                                                      1   0.00%
│   ├── output_buffer.1                                                                           128   0.27%
│   ├── pCCRndCryptoMutex                                                                           4   0.01%
│   ├── platform_abort_apis                                                                         8   0.02%
│   ├── platform_mutex_apis                                                                        16   0.03%
│   ├── platform_mutexes                                                                           20   0.04%
│   ├── poll_out_lock.0                                                                             4   0.01%
│   ├── random_seed_buffer                                                                        104   0.22%
│   ├── random_seed_filled                                                                          4   0.01%
│   ├── rndState.0                                                                                  4   0.01%
│   ├── rndWorkBuffer.2                                                                           544   1.16%
│   ├── rndWorkbuff.0                                                                             544   1.16%
│   ├── sched_spinlock                                                                              4   0.01%
│   ├── seed.1                                                                                    384   0.82%
│   ├── signed_data.2                                                                            1024   2.18%
│   ├── trngParams.1                                                                               40   0.08%
│   ├── use_count                                                                                   4   0.01%
│   ├── wait_q.0                                                                                    8   0.02%
│   ├── z_idle_threads                                                                            184   0.39%
│   ├── z_interrupt_stacks                                                                       2048   4.35%
│   └── z_main_thread                                                                             184   0.39%
├── /                                                                                            6637  14.10%
│   └── workspaces                                                                               6637  14.10%
│       └── concord                                                                              6637  14.10%
│           └── apps                                                                             6637  14.10%
│               └── dns-sec                                                                      6637  14.10%
│                   ├── dns_sec                                                                  6629  14.08%
│                   │   └── zephyr                                                               6629  14.08%
│                   │       └── src                                                              6629  14.08%
│                   │           ├── dns_sec.c                                                       9   0.02%
│                   │           │   ├── g_crypto_functions                                          8   0.02%
│                   │           │   └── g_crypto_initialized                                        1   0.00%
│                   │           └── prv                                                          6620  14.06%
│                   │               └── query.c                                                  6620  14.06%
│                   │                   ├── dns_heap                                               24   0.05%
│                   │                   ├── kheap_dns_heap                                       5096  10.82%
│                   │                   └── net_buffer                                           1500   3.19%
│                   └── src                                                                         8   0.02%
│                       └── main.c                                                                  8   0.02%
│                           └── custom_crypto_funcs                                                 8   0.02%
├── WORKSPACE                                                                                    1614   3.43%
│   ├── modules                                                                                   188   0.40%
│   │   └── hal                                                                                   188   0.40%
│   │       └── nordic                                                                            188   0.40%
│   │           └── nrfx                                                                          188   0.40%
│   │               └── drivers                                                                   188   0.40%
│   │                   └── src                                                                   188   0.40%
│   │                       ├── nrfx_clock.c                                                        8   0.02%
│   │                       │   └── m_clock_cb                                                      8   0.02%
│   │                       ├── nrfx_gpiote.c                                                     124   0.26%
│   │                       │   └── m_cb                                                          124   0.26%
│   │                       ├── nrfx_ppi.c                                                          4   0.01%
│   │                       │   └── m_channels_allocated                                            4   0.01%
│   │                       └── nrfx_twim.c                                                        52   0.11%
│   │                           └── m_cb                                                           52   0.11%
│   ├── nrf                                                                                         2   0.00%
│   │   └── drivers                                                                                 2   0.00%
│   │       └── entropy                                                                             2   0.00%
│   │           └── entropy_cc3xx.c                                                                 2   0.00%
│   │               └── __devstate_dts_ord_98                                                       2   0.00%
│   └── nrfxlib                                                                                  1424   3.02%
│       └── crypto                                                                               1424   3.02%
│           └── nrf_cc310_platform                                                               1424   3.02%
│               └── src                                                                          1424   3.02%
│                   └── nrf_cc3xx_platform_mutex_zephyr.c                                        1424   3.02%
│                       ├── asym_mutex                                                              8   0.02%
│                       ├── asym_mutex_int                                                         20   0.04%
│                       ├── mutex_slab                                                             32   0.07%
│                       ├── mutex_slab_buffer                                                    1280   2.72%
│                       ├── power_mutex                                                             8   0.02%
│                       ├── power_mutex_int                                                        20   0.04%
│                       ├── rng_mutex                                                               8   0.02%
│                       ├── rng_mutex_int                                                          20   0.04%
│                       ├── sym_mutex                                                               8   0.02%
│                       └── sym_mutex_int                                                          20   0.04%
└── ZEPHYR_BASE                                                                                 31488  66.88%
    ├── arch                                                                                        1   0.00%
    │   └── arm                                                                                     1   0.00%
    │       └── core                                                                                1   0.00%
    │           └── aarch32                                                                         1   0.00%
    │               └── mpu                                                                         1   0.00%
    │                   └── arm_mpu.c                                                               1   0.00%
    │                       └── static_regions_num                                                  1   0.00%
    ├── drivers                                                                                   369   0.78%
    │   ├── clock_control                                                                          94   0.20%
    │   │   └── clock_control_nrf.c                                                                94   0.20%
    │   │       ├── __devstate_dts_ord_57                                                           2   0.00%
    │   │       ├── data                                                                           88   0.19%
    │   │       └── hfclk_users                                                                     4   0.01%
    │   ├── entropy                                                                                86   0.18%
    │   │   └── entropy_nrf5.c                                                                     86   0.18%
    │   │       ├── __devstate_dts_ord_80                                                           2   0.00%
    │   │       └── entropy_nrf5_data                                                              84   0.18%
    │   ├── gpio                                                                                   28   0.06%
    │   │   └── gpio_nrfx.c                                                                        28   0.06%
    │   │       ├── __devstate_dts_ord_13                                                           2   0.00%
    │   │       ├── __devstate_dts_ord_18                                                           2   0.00%
    │   │       ├── gpio_nrfx_p0_data                                                              12   0.03%
    │   │       └── gpio_nrfx_p1_data                                                              12   0.03%
    │   ├── i2c                                                                                    74   0.16%
    │   │   └── i2c_nrfx_twim.c                                                                    74   0.16%
    │   │       ├── __devstate_dts_ord_108                                                          2   0.00%
    │   │       ├── twim_0_data                                                                    56   0.12%
    │   │       └── twim_0_msg_buf                                                                 16   0.03%
    │   ├── serial                                                                                 42   0.09%
    │   │   ├── uart_nrfx_uart.c                                                                   10   0.02%
    │   │   │   ├── __devstate_dts_ord_93                                                           2   0.00%
    │   │   │   └── uart_nrfx_uart0_data                                                            8   0.02%
    │   │   └── uart_nrfx_uarte.c                                                                  32   0.07%
    │   │       ├── __devstate_dts_ord_94                                                           2   0.00%
    │   │       ├── uarte1_char_out                                                                 1   0.00%
    │   │       ├── uarte1_rx_data                                                                  1   0.00%
    │   │       └── uarte_1_data                                                                   28   0.06%
    │   └── timer                                                                                  45   0.10%
    │       └── nrf_rtc_timer.c                                                                    45   0.10%
    │           ├── anchor                                                                          8   0.02%
    │           ├── cc_data                                                                        16   0.03%
    │           ├── force_isr_mask                                                                  4   0.01%
    │           ├── int_mask                                                                        4   0.01%
    │           ├── last_count                                                                      8   0.02%
    │           ├── overflow_cnt                                                                    4   0.01%
    │           └── sys_busy                                                                        1   0.00%
    ├── kernel                                                                                  11718  24.89%
    │   ├── condvar.c                                                                               4   0.01%
    │   │   └── lock                                                                                4   0.01%
    │   ├── init.c                                                                              10321  21.92%
    │   │   ├── z_idle_stacks                                                                     320   0.68%
    │   │   ├── z_main_stack                                                                    10000  21.24%
    │   │   └── z_sys_post_kernel                                                                   1   0.00%
    │   ├── mempool.c                                                                             280   0.59%
    │   │   ├── _system_heap                                                                       24   0.05%
    │   │   └── kheap__system_heap                                                                256   0.54%
    │   ├── mutex.c                                                                                 4   0.01%
    │   │   └── lock                                                                                4   0.01%
    │   ├── poll.c                                                                                  4   0.01%
    │   │   └── lock                                                                                4   0.01%
    │   ├── sched.c                                                                                37   0.08%
    │   │   ├── pending_current                                                                     4   0.01%
    │   │   ├── slice_expired                                                                       1   0.00%
    │   │   ├── slice_max_prio                                                                      4   0.01%
    │   │   ├── slice_ticks                                                                         4   0.01%
    │   │   └── slice_timeouts                                                                     24   0.05%
    │   ├── sem.c                                                                                   4   0.01%
    │   │   └── lock                                                                                4   0.01%
    │   ├── system_work_q.c                                                                      1024   2.18%
    │   │   └── sys_work_q_stack                                                                 1024   2.18%
    │   ├── thread.c                                                                                4   0.01%
    │   │   └── z_thread_monitor_lock                                                               4   0.01%
    │   ├── timeout.c                                                                              24   0.05%
    │   │   ├── announce_remaining                                                                  4   0.01%
    │   │   ├── curr_tick                                                                           8   0.02%
    │   │   ├── timeout_list                                                                        8   0.02%
    │   │   └── timeout_lock                                                                        4   0.01%
    │   └── work.c                                                                                 12   0.03%
    │       ├── lock                                                                                4   0.01%
    │       └── pending_cancels                                                                     8   0.02%
    ├── lib                                                                                       176   0.37%
    │   ├── libc                                                                                   24   0.05%
    │   │   └── newlib                                                                             24   0.05%
    │   │       └── libc-hooks.c                                                                   24   0.05%
    │   │           ├── __lock___malloc_recursive_mutex                                            20   0.04%
    │   │           └── _stdout_hook                                                                4   0.01%
    │   └── os                                                                                    152   0.32%
    │       ├── fdtable.c                                                                         148   0.31%
    │       │   ├── fdtable                                                                       128   0.27%
    │       │   └── fdtable_lock                                                                   20   0.04%
    │       └── printk.c                                                                            4   0.01%
    │           └── _char_out                                                                       4   0.01%
    └── subsys                                                                                  19224  40.83%
        ├── debug                                                                                  61   0.13%
        │   └── thread_info.c                                                                      61   0.13%
        │       ├── _kernel_thread_info_num_offsets                                                 4   0.01%
        │       ├── _kernel_thread_info_offsets                                                    56   0.12%
        │       └── _kernel_thread_info_size_t_size                                                 1   0.00%
        ├── logging                                                                               128   0.27%
        │   ├── backends                                                                           26   0.06%
        │   │   └── log_backend_uart.c                                                             26   0.06%
        │   │       ├── backend_cb_log_backend_uart                                                 8   0.02%
        │   │       ├── in_panic                                                                    1   0.00%
        │   │       ├── log_format_current                                                          4   0.01%
        │   │       ├── log_output_uart_control_block                                              12   0.03%
        │   │       └── uart_output_buf                                                             1   0.00%
        │   ├── log_core.c                                                                         94   0.20%
        │   │   ├── backend_attached                                                                1   0.00%
        │   │   ├── buffered_cnt                                                                    4   0.01%
        │   │   ├── dropped_cnt                                                                     4   0.01%
        │   │   ├── initialized                                                                     4   0.01%
        │   │   ├── log_buffer                                                                     68   0.14%
        │   │   ├── log_msg_ptr                                                                     4   0.01%
        │   │   ├── panic_mode                                                                      1   0.00%
        │   │   ├── timestamp_freq                                                                  4   0.01%
        │   │   └── timestamp_func                                                                  4   0.01%
        │   └── log_output.c                                                                        8   0.02%
        │       ├── freq                                                                            4   0.01%
        │       └── timestamp_div                                                                   4   0.01%
        ├── net                                                                                 18987  40.33%
        │   ├── ip                                                                              17832  37.88%
        │   │   ├── connection.c                                                                  580   1.23%
        │   │   │   ├── conn_lock                                                                  20   0.04%
        │   │   │   ├── conn_unused                                                                 8   0.02%
        │   │   │   ├── conn_used                                                                   8   0.02%
        │   │   │   └── conns                                                                     544   1.16%
        │   │   ├── dhcpv4.c                                                                       88   0.19%
        │   │   │   ├── dhcpv4_ifaces                                                               8   0.02%
        │   │   │   ├── lock                                                                       20   0.04%
        │   │   │   ├── mgmt4_cb                                                                   12   0.03%
        │   │   │   └── timeout_work                                                               48   0.10%
        │   │   ├── icmpv4.c                                                                       20   0.04%
        │   │   │   ├── echo_request_handler                                                       12   0.03%
        │   │   │   └── handlers                                                                    8   0.02%
        │   │   ├── icmpv6.c                                                                       20   0.04%
        │   │   │   ├── echo_request_handler                                                       12   0.03%
        │   │   │   └── handlers                                                                    8   0.02%
        │   │   ├── ipv6_mld.c                                                                     12   0.03%
        │   │   │   └── mld_query_input_handler                                                    12   0.03%
        │   │   ├── ipv6_nbr.c                                                                    844   1.79%
        │   │   │   ├── ipv6_nd_reachable_timer                                                    48   0.10%
        │   │   │   ├── ipv6_ns_reply_timer                                                        48   0.10%
        │   │   │   ├── na_input_handler                                                           12   0.03%
        │   │   │   ├── nbr_lock                                                                   24   0.05%
        │   │   │   ├── net_neighbor                                                               12   0.03%
        │   │   │   ├── net_neighbor_pool                                                         672   1.43%
        │   │   │   ├── ns_input_handler                                                           12   0.03%
        │   │   │   ├── ra_input_handler                                                           12   0.03%
        │   │   │   └── stale_counter                                                               4   0.01%
        │   │   ├── nbr.c                                                                          72   0.15%
        │   │   │   └── net_neighbor_lladdr                                                        72   0.15%
        │   │   ├── net_context.c                                                                1176   2.50%
        │   │   │   ├── contexts                                                                 1152   2.45%
        │   │   │   └── contexts_lock                                                              24   0.05%
        │   │   ├── net_if.c                                                                      756   1.61%
        │   │   │   ├── active_address_lifetime_timers                                              8   0.02%
        │   │   │   ├── active_dad_timers                                                           8   0.02%
        │   │   │   ├── active_prefix_lifetime_timers                                               8   0.02%
        │   │   │   ├── active_router_timers                                                        8   0.02%
        │   │   │   ├── active_rs_timers                                                            8   0.02%
        │   │   │   ├── address_lifetime_timer                                                     48   0.10%
        │   │   │   ├── dad_timer                                                                  48   0.10%
        │   │   │   ├── default_iface                                                               4   0.01%
        │   │   │   ├── ipv4_addresses                                                             88   0.19%
        │   │   │   ├── ipv6_addresses                                                            276   0.59%
        │   │   │   ├── link_callbacks                                                              8   0.02%
        │   │   │   ├── lock                                                                       20   0.04%
        │   │   │   ├── mcast_monitor_callbacks                                                     8   0.02%
        │   │   │   ├── prefix_lifetime_timer                                                      48   0.10%
        │   │   │   ├── router_timer                                                               48   0.10%
        │   │   │   ├── routers                                                                    72   0.15%
        │   │   │   └── rs_timer                                                                   48   0.10%
        │   │   ├── net_mgmt.c                                                                   1104   2.34%
        │   │   │   ├── _k_fifo_buf_event_msgq                                                     40   0.08%
        │   │   │   ├── event_callbacks                                                             8   0.02%
        │   │   │   ├── event_msgq                                                                 52   0.11%
        │   │   │   ├── global_event_mask                                                           4   0.01%
        │   │   │   ├── mgmt_stack                                                                768   1.63%
        │   │   │   ├── mgmt_thread_data                                                          184   0.39%
        │   │   │   ├── net_mgmt_callback_lock                                                     20   0.04%
        │   │   │   ├── net_mgmt_event_lock                                                        20   0.04%
        │   │   │   └── new_event                                                                   8   0.02%
        │   │   ├── net_pkt.c                                                                    5704  12.12%
        │   │   │   ├── _k_mem_slab_buf_rx_pkts                                                   272   0.58%
        │   │   │   ├── _k_mem_slab_buf_tx_pkts                                                   272   0.58%
        │   │   │   ├── _net_buf_rx_bufs                                                          448   0.95%
        │   │   │   ├── _net_buf_tx_bufs                                                          448   0.95%
        │   │   │   ├── net_buf_data_rx_bufs                                                     2048   4.35%
        │   │   │   ├── net_buf_data_tx_bufs                                                     2048   4.35%
        │   │   │   ├── rx_bufs                                                                    52   0.11%
        │   │   │   ├── rx_pkts                                                                    32   0.07%
        │   │   │   ├── tx_bufs                                                                    52   0.11%
        │   │   │   └── tx_pkts                                                                    32   0.07%
        │   │   ├── net_tc.c                                                                     1728   3.67%
        │   │   │   ├── rx_classes                                                                224   0.48%
        │   │   │   └── rx_stack                                                                 1504   3.19%
        │   │   ├── route.c                                                                       896   1.90%
        │   │   │   ├── active_route_lifetime_timers                                                8   0.02%
        │   │   │   ├── lock                                                                       20   0.04%
        │   │   │   ├── net_nbr_routes                                                             12   0.03%
        │   │   │   ├── net_route_entries_pool                                                    576   1.22%
        │   │   │   ├── net_route_nexthop_pool                                                    224   0.48%
        │   │   │   ├── route_lifetime_timer                                                       48   0.10%
        │   │   │   └── routes                                                                      8   0.02%
        │   │   └── tcp.c                                                                        4832  10.26%
        │   │       ├── _k_mem_slab_buf_tcp_conns_slab                                           3504   7.44%
        │   │       ├── tcp_conns                                                                   8   0.02%
        │   │       ├── tcp_conns_slab                                                             32   0.07%
        │   │       ├── tcp_fin_timeout_ms                                                          4   0.01%
        │   │       ├── tcp_lock                                                                   20   0.04%
        │   │       ├── tcp_recv_cb                                                                 4   0.01%
        │   │       ├── tcp_send_cb                                                                 4   0.01%
        │   │       ├── tcp_work_q                                                                216   0.46%
        │   │       ├── unique_key                                                                 16   0.03%
        │   │       └── work_q_stack                                                             1024   2.18%
        │   └── lib                                                                              1155   2.45%
        │       ├── config                                                                         76   0.16%
        │       │   └── init.c                                                                     76   0.16%
        │       │       ├── counter                                                                24   0.05%
        │       │       ├── mgmt4_cb                                                               12   0.03%
        │       │       ├── mgmt_iface_cb                                                          12   0.03%
        │       │       ├── services_flags                                                          4   0.01%
        │       │       └── waiter                                                                 24   0.05%
        │       └── dns                                                                          1079   2.29%
        │           └── resolve.c                                                                1079   2.29%
        │               ├── _net_buf_dns_msg_pool                                                  24   0.05%
        │               ├── _net_buf_dns_qname_pool                                                24   0.05%
        │               ├── dns_default_ctx                                                       160   0.34%
        │               ├── dns_msg_pool                                                           52   0.11%
        │               ├── dns_qname_pool                                                         52   0.11%
        │               ├── net_buf_data_dns_msg_pool                                             512   1.09%
        │               └── net_buf_data_dns_qname_pool                                           255   0.54%
        └── pm                                                                                     48   0.10%
            ├── pm.c                                                                               44   0.09%
            │   ├── pm_forced_state_lock                                                            4   0.01%
            │   ├── pm_notifier_lock                                                                4   0.01%
            │   ├── pm_notifiers                                                                    8   0.02%
            │   ├── z_cpus_pm_forced_state                                                         12   0.03%
            │   ├── z_cpus_pm_state                                                                12   0.03%
            │   └── z_post_ops_required                                                             4   0.01%
            └── policy.c                                                                            4   0.01%
                └── max_latency_ticks                                                               4   0.01%
==============================================================================================================
                                                                                                47079
