-- west build: running target rom_report
[0/1] cd /workspaces/concord/apps/dns-sec/build && /usr/bin/python3.10 /ncs/zephyr/scripts/footprint/size_report -k /workspaces/concord/apps/dns-sec/build/zephyr/zephyr.elf -z /ncs/zephyr -o /workspaces/concord/apps/dns-sec/build --workspace=/ncs -d 99 rom
Path                                                                                             Size    %  
==============================================================================================================
Root                                                                                           191792 100.00%
├── (hidden)                                                                                    24928  13.00%
├── (no paths)                                                                                  14927   7.78%
│   ├── CCAsymCryptoMutex                                                                           4   0.00%
│   ├── CCPowerMutex                                                                                4   0.00%
│   ├── CCRndCryptoMutex                                                                            4   0.00%
│   ├── CCSymCryptoMutex                                                                            4   0.00%
│   ├── CC_HalClearInterruptBit                                                                    28   0.01%
│   ├── CC_HalInit                                                                                  4   0.00%
│   ├── CC_HalMaskInterrupt                                                                        12   0.01%
│   ├── CC_HalTerminate                                                                             4   0.00%
│   ├── CC_HalWaitInterrupt                                                                        12   0.01%
│   ├── CC_HalWaitInterruptRND                                                                     12   0.01%
│   ├── CC_LibInit                                                                                192   0.10%
│   ├── CC_PalAbort                                                                                52   0.03%
│   ├── CC_PalDataBufferAttrGet                                                                     6   0.00%
│   ├── CC_PalDmaInit                                                                               4   0.00%
│   ├── CC_PalDmaTerminate                                                                          2   0.00%
│   ├── CC_PalInit                                                                                 92   0.05%
│   ├── CC_PalMemCopyPlat                                                                           4   0.00%
│   ├── CC_PalMemSetPlat                                                                            4   0.00%
│   ├── CC_PalMemSetZeroPlat                                                                        8   0.00%
│   ├── CC_PalMutexCreate                                                                          20   0.01%
│   ├── CC_PalMutexDestroy                                                                         20   0.01%
│   ├── CC_PalMutexLock                                                                            16   0.01%
│   ├── CC_PalMutexUnlock                                                                          20   0.01%
│   ├── CC_PalPowerSaveModeInit                                                                    60   0.03%
│   ├── CC_PalPowerSaveModeSelect                                                                 132   0.07%
│   ├── CC_PalTerminate                                                                            52   0.03%
│   ├── CC_PalTrngParamGet                                                                        168   0.09%
│   ├── CC_PalWaitInterrupt                                                                        24   0.01%
│   ├── CC_PalWaitInterruptRND                                                                     44   0.02%
│   ├── CSWTCH.10                                                                                  28   0.01%
│   ├── FinishAesDrv                                                                              596   0.31%
│   ├── FinishHashDrv                                                                             112   0.06%
│   ├── HASH_LARVAL_SHA1                                                                           20   0.01%
│   ├── HASH_LARVAL_SHA224                                                                         32   0.02%
│   ├── HASH_LARVAL_SHA256                                                                         32   0.02%
│   ├── InitAes.part.0                                                                            228   0.12%
│   ├── InitHashDrv                                                                                80   0.04%
│   ├── LLF_RND_AdaptiveProportionTest                                                            132   0.07%
│   ├── LLF_RND_GetFastestRosc                                                                     32   0.02%
│   ├── LLF_RND_GetRoscSampleCnt                                                                   52   0.03%
│   ├── LLF_RND_GetTrngSource                                                                      22   0.01%
│   ├── LLF_RND_RepetitionCounterTest                                                              96   0.05%
│   ├── LLF_RND_RunTrngStartupTest                                                                 26   0.01%
│   ├── LLF_RND_TurnOffTrng                                                                        24   0.01%
│   ├── LLF_RND_WaitRngInterrupt                                                                   32   0.02%
│   ├── LoadAesKey                                                                                168   0.09%
│   ├── ProcessAesDrv                                                                             872   0.45%
│   ├── ProcessHashDrv                                                                            556   0.29%
│   ├── RNG_PLAT_SetUserRngParameters                                                             116   0.06%
│   ├── RndStartupTest.constprop.0                                                                152   0.08%
│   ├── SetDataBuffersInfo                                                                        104   0.05%
│   ├── UtilCmacBuildDataForDerivation                                                            192   0.10%
│   ├── __aeabi_ldiv0                                                                               2   0.00%
│   ├── __device_dts_ord_108                                                                       24   0.01%
│   ├── __device_dts_ord_13                                                                        24   0.01%
│   ├── __device_dts_ord_18                                                                        24   0.01%
│   ├── __device_dts_ord_57                                                                        24   0.01%
│   ├── __device_dts_ord_80                                                                        24   0.01%
│   ├── __device_dts_ord_93                                                                        24   0.01%
│   ├── __device_dts_ord_94                                                                        24   0.01%
│   ├── __device_dts_ord_98                                                                        24   0.01%
│   ├── __func__.0                                                                                 72   0.04%
│   ├── __func__.1                                                                                 37   0.02%
│   ├── __func__.10                                                                                27   0.01%
│   ├── __func__.11                                                                                27   0.01%
│   ├── __func__.12                                                                                25   0.01%
│   ├── __func__.13                                                                                19   0.01%
│   ├── __func__.14                                                                                21   0.01%
│   ├── __func__.15                                                                                18   0.01%
│   ├── __func__.16                                                                                26   0.01%
│   ├── __func__.2                                                                                 30   0.02%
│   ├── __func__.3                                                                                 29   0.02%
│   ├── __func__.4                                                                                 27   0.01%
│   ├── __func__.5                                                                                 28   0.01%
│   ├── __func__.6                                                                                 25   0.01%
│   ├── __func__.7                                                                                 19   0.01%
│   ├── __func__.8                                                                                 21   0.01%
│   ├── __func__.9                                                                                 18   0.01%
│   ├── __malloc_lock                                                                              12   0.01%
│   ├── __malloc_unlock                                                                            12   0.01%
│   ├── __memcpy_chk                                                                               38   0.02%
│   ├── __udivmoddi4                                                                              672   0.35%
│   ├── _ctype_                                                                                   257   0.13%
│   ├── _free_r                                                                                   148   0.08%
│   ├── _impure_ptr                                                                                 4   0.00%
│   ├── _strerror_r                                                                               972   0.51%
│   ├── _strtol_l.constprop.0                                                                     252   0.13%
│   ├── _strtoul_l.constprop.0                                                                    228   0.12%
│   ├── _sw_isr_table                                                                             384   0.20%
│   ├── _user_strerror                                                                              4   0.00%
│   ├── addr.0                                                                                      4   0.00%
│   ├── addr.1                                                                                      4   0.00%
│   ├── all_nodes_mcast_group.0                                                                    16   0.01%
│   ├── block_cipher_df                                                                           464   0.24%
│   ├── cc_mbedtls_aes_crypt_ecb                                                                   84   0.04%
│   ├── cc_mbedtls_aes_free                                                                        12   0.01%
│   ├── cc_mbedtls_aes_init                                                                        32   0.02%
│   ├── cc_mbedtls_aes_setkey_enc                                                                  52   0.03%
│   ├── cc_mbedtls_ctr_drbg_init                                                                   44   0.02%
│   ├── cc_mbedtls_ctr_drbg_random_with_add                                                       484   0.25%
│   ├── cc_mbedtls_ctr_drbg_seed                                                                  152   0.08%
│   ├── cc_mbedtls_entropy_func                                                                   268   0.14%
│   ├── cc_mbedtls_entropy_init                                                                   136   0.07%
│   ├── cc_mbedtls_sha256                                                                          80   0.04%
│   ├── cc_mbedtls_sha256_finish                                                                   70   0.04%
│   ├── cc_mbedtls_sha256_free                                                                     10   0.01%
│   ├── cc_mbedtls_sha256_init                                                                     40   0.02%
│   ├── cc_mbedtls_sha256_starts                                                                   38   0.02%
│   ├── cc_mbedtls_sha256_update                                                                   82   0.04%
│   ├── chk_fail_msg.0                                                                             30   0.02%
│   ├── ctr_drbg_update_internal                                                                  326   0.17%
│   ├── data.0                                                                                      3   0.00%
│   ├── delay_machine_code.0                                                                        6   0.00%
│   ├── dnssec_error_strings.0                                                                     40   0.02%
│   ├── entropy_gather_internal.part.0                                                            120   0.06%
│   ├── entropy_update                                                                            124   0.06%
│   ├── free                                                                                       16   0.01%
│   ├── getTrngSource                                                                             692   0.36%
│   ├── impure_data                                                                                96   0.05%
│   ├── in6addr_any                                                                                16   0.01%
│   ├── invalid_aes_256_bit_key                                                                     4   0.00%
│   ├── kmu_derive_cmac                                                                           284   0.15%
│   ├── kmu_use_kdr_key                                                                            20   0.01%
│   ├── kmu_validate_kdr_slot_and_size                                                             28   0.01%
│   ├── kmu_validate_slot_and_size                                                                 28   0.01%
│   ├── levels.0                                                                                   24   0.01%
│   ├── mbedtls_ctr_drbg_reseed_internal                                                          196   0.10%
│   ├── mbedtls_hardware_poll                                                                     252   0.13%
│   ├── mbedtls_mutex_init                                                                          4   0.00%
│   ├── mbedtls_mutex_lock                                                                          4   0.00%
│   ├── mbedtls_mutex_unlock                                                                        4   0.00%
│   ├── mbedtls_platform_zeroize                                                                   20   0.01%
│   ├── mbedtls_sha_finish_internal                                                                92   0.05%
│   ├── mbedtls_sha_starts_internal                                                                38   0.02%
│   ├── mbedtls_sha_update_internal                                                               492   0.26%
│   ├── mbedtls_zeroize_internal                                                                   20   0.01%
│   ├── memcmp                                                                                     32   0.02%
│   ├── memcpy                                                                                     28   0.01%
│   ├── memmove                                                                                    52   0.03%
│   ├── memset                                                                                     16   0.01%
│   ├── mpu_config                                                                                  8   0.00%
│   ├── mutex_free                                                                                 52   0.03%
│   ├── mutex_init                                                                                 44   0.02%
│   ├── mutex_lock                                                                                 84   0.04%
│   ├── mutex_unlock                                                                               68   0.04%
│   ├── name.1                                                                                     28   0.01%
│   ├── net_buf_fixed_cb                                                                           12   0.01%
│   ├── nrf_cc3xx_platform_abort                                                                   36   0.02%
│   ├── nrf_cc3xx_platform_ctr_drbg_get                                                            68   0.04%
│   ├── nrf_cc3xx_platform_ctr_drbg_init                                                           96   0.05%
│   ├── nrf_cc3xx_platform_init                                                                    68   0.04%
│   ├── nrf_cc3xx_platform_set_abort                                                               16   0.01%
│   ├── nrf_cc3xx_platform_set_mutexes                                                            116   0.06%
│   ├── pCCRndCryptoMutex                                                                           4   0.00%
│   ├── platform_abort_apis                                                                         8   0.00%
│   ├── platform_mutex_apis                                                                        16   0.01%
│   ├── platform_mutexes                                                                           20   0.01%
│   ├── startTrngHW                                                                               320   0.17%
│   ├── strchr                                                                                     26   0.01%
│   ├── strcmp                                                                                     20   0.01%
│   ├── strcspn                                                                                    34   0.02%
│   ├── strerror                                                                                   20   0.01%
│   ├── strlen                                                                                     16   0.01%
│   ├── strncpy                                                                                    38   0.02%
│   ├── strnlen                                                                                    24   0.01%
│   ├── strrchr                                                                                    40   0.02%
│   ├── strtol                                                                                     20   0.01%
│   ├── strtoul                                                                                    20   0.01%
│   ├── transitions.0                                                                              12   0.01%
│   ├── wait_q.0                                                                                    8   0.00%
│   └── write_invalid_key                                                                          48   0.03%
├── /                                                                                           14466   7.54%
│   ├── usr                                                                                       140   0.07%
│   │   └── home                                                                                  140   0.07%
│   │       └── zephyr-sdk-0.16.1                                                                 140   0.07%
│   │           └── arm-zephyr-eabi                                                               140   0.07%
│   │               └── arm-zephyr-eabi                                                           140   0.07%
│   │                   └── sys-include                                                           140   0.07%
│   │                       ├── ssp                                                                28   0.01%
│   │                       │   └── ssp.h                                                          28   0.01%
│   │                       │       └── __chk_fail                                                 28   0.01%
│   │                       └── sys                                                               112   0.06%
│   │                           ├── errno.h                                                         8   0.00%
│   │                           │   └── __errno                                                     8   0.00%
│   │                           └── lock.h                                                        104   0.05%
│   │                               ├── __retarget_lock_acquire_recursive                          56   0.03%
│   │                               └── __retarget_lock_release_recursive                          48   0.03%
│   └── workspaces                                                                              14326   7.47%
│       └── concord                                                                             14326   7.47%
│           └── apps                                                                            14326   7.47%
│               └── dns-sec                                                                     14326   7.47%
│                   ├── dns_sec                                                                 13502   7.04%
│                   │   └── zephyr                                                              13502   7.04%
│                   │       └── src                                                             13502   7.04%
│                   │           ├── dns_sec.c                                                     838   0.44%
│                   │           │   ├── check_info_record_in_response                             112   0.06%
│                   │           │   ├── check_rrsig_record_in_response                            112   0.06%
│                   │           │   ├── dnssec_err_str                                             24   0.01%
│                   │           │   ├── dnssec_init_crypto_functions                               76   0.04%
│                   │           │   ├── freesecaddrinfo                                            42   0.02%
│                   │           │   ├── getsecaddrinfo                                            464   0.24%
│                   │           │   └── log_const_dns_sec                                           8   0.00%
│                   │           └── prv                                                         12664   6.60%
│                   │               ├── free.c                                                    424   0.22%
│                   │               │   ├── dnssec_free_query                                      64   0.03%
│                   │               │   ├── free_additional_data                                   20   0.01%
│                   │               │   ├── free_questions                                        100   0.05%
│                   │               │   ├── free_request                                           56   0.03%
│                   │               │   ├── free_resource_records                                 116   0.06%
│                   │               │   └── free_response                                          68   0.04%
│                   │               ├── net.c                                                    8130   4.24%
│                   │               │   ├── calculate_key_tag                                      38   0.02%
│                   │               │   ├── dns_decode_header                                     572   0.30%
│                   │               │   ├── dns_decode_questions                                  528   0.28%
│                   │               │   ├── dns_decode_record_data_a                              112   0.06%
│                   │               │   ├── dns_decode_record_data_aaaa                           124   0.06%
│                   │               │   ├── dns_decode_record_data_dnskey                         484   0.25%
│                   │               │   ├── dns_decode_record_data_opt                            360   0.19%
│                   │               │   ├── dns_decode_record_data_rrsig                          460   0.24%
│                   │               │   ├── dns_decode_record_data_soa                            268   0.14%
│                   │               │   ├── dns_decode_records                                    696   0.36%
│                   │               │   ├── dns_encode_questions                                  388   0.20%
│                   │               │   ├── dns_encode_record_data_a                              288   0.15%
│                   │               │   ├── dns_encode_record_data_opt                            468   0.24%
│                   │               │   ├── dns_encode_records                                    620   0.32%
│                   │               │   ├── dns_header_encode                                     680   0.35%
│                   │               │   ├── dnssec_decode_dns_response                            416   0.22%
│                   │               │   ├── dnssec_encode_dns_request                             356   0.19%
│                   │               │   ├── dnssec_getresolver                                     80   0.04%
│                   │               │   ├── dnssec_socket_create                                  228   0.12%
│                   │               │   ├── dnssec_socket_recv                                    116   0.06%
│                   │               │   ├── dnssec_socket_send                                    168   0.09%
│                   │               │   ├── get_domain_name                                       252   0.13%
│                   │               │   ├── get_uint32                                             44   0.02%
│                   │               │   ├── handle_dns_name                                       172   0.09%
│                   │               │   ├── put_bytes                                              38   0.02%
│                   │               │   ├── put_domain_name                                        58   0.03%
│                   │               │   ├── put_uint16                                             36   0.02%
│                   │               │   ├── put_uint32                                             56   0.03%
│                   │               │   └── put_uint8                                              24   0.01%
│                   │               ├── query.c                                                  1264   0.66%
│                   │               │   ├── create_dns_request                                    808   0.42%
│                   │               │   ├── dns_heap                                               24   0.01%
│                   │               │   ├── dnssec_do_query                                       424   0.22%
│                   │               │   └── dnssec_get_heap                                         8   0.00%
│                   │               ├── result.c                                                  452   0.24%
│                   │               │   ├── dnssec_set_result                                     160   0.08%
│                   │               │   └── set_record_type_a                                     292   0.15%
│                   │               ├── signature.c                                              1460   0.76%
│                   │               │   ├── dnssec_check_signature                                320   0.17%
│                   │               │   ├── encode_info_record                                    464   0.24%
│                   │               │   └── prepare_message_data                                  676   0.35%
│                   │               ├── string.c                                                  266   0.14%
│                   │               │   ├── dnssec_convert_str_to_dns_format                       54   0.03%
│                   │               │   ├── dnssec_get_zone_str_from_domain                       144   0.08%
│                   │               │   └── format_domain_name                                     68   0.04%
│                   │               └── validate.c                                                668   0.35%
│                   │                   ├── dnssec_validate_record                                332   0.17%
│                   │                   ├── extract_dnskey                                        128   0.07%
│                   │                   ├── extract_info_record                                   104   0.05%
│                   │                   └── extract_rrsig                                         104   0.05%
│                   └── src                                                                       824   0.43%
│                       └── main.c                                                                824   0.43%
│                           ├── custom_crypto_funcs                                                 8   0.00%
│                           ├── dump_addrinfo                                                     108   0.06%
│                           ├── hash                                                              228   0.12%
│                           ├── log_const_app                                                       8   0.00%
│                           ├── main                                                              192   0.10%
│                           ├── print_addresses                                                   228   0.12%
│                           └── verify                                                             52   0.03%
├── OUTPUT_DIR                                                                                    242   0.13%
│   └── zephyr                                                                                    242   0.13%
│       ├── dev_handles.c                                                                          48   0.03%
│       │   ├── __devicehdl_dts_ord_108                                                             6   0.00%
│       │   ├── __devicehdl_dts_ord_13                                                              6   0.00%
│       │   ├── __devicehdl_dts_ord_18                                                              6   0.00%
│       │   ├── __devicehdl_dts_ord_57                                                              6   0.00%
│       │   ├── __devicehdl_dts_ord_80                                                              6   0.00%
│       │   ├── __devicehdl_dts_ord_93                                                              6   0.00%
│       │   ├── __devicehdl_dts_ord_94                                                              6   0.00%
│       │   └── __devicehdl_dts_ord_98                                                              6   0.00%
│       ├── isr_tables.c                                                                          192   0.10%
│       │   └── _irq_vector_table                                                                 192   0.10%
│       └── misc                                                                                    2   0.00%
│           └── generated                                                                           2   0.00%
│               └── configs.c                                                                       2   0.00%
│                   └── _ConfigAbsSyms                                                              2   0.00%
├── WORKSPACE                                                                                   17396   9.07%
│   ├── modules                                                                                 16404   8.55%
│   │   ├── crypto                                                                               8272   4.31%
│   │   │   ├── mbedtls                                                                          3300   1.72%
│   │   │   │   └── library                                                                      3300   1.72%
│   │   │   │       └── md5.c                                                                    3300   1.72%
│   │   │   │           ├── mbedtls_internal_md5_process                                         2800   1.46%
│   │   │   │           ├── mbedtls_md5                                                            66   0.03%
│   │   │   │           ├── mbedtls_md5_finish                                                    226   0.12%
│   │   │   │           ├── mbedtls_md5_free                                                       14   0.01%
│   │   │   │           ├── mbedtls_md5_init                                                       12   0.01%
│   │   │   │           ├── mbedtls_md5_starts                                                     44   0.02%
│   │   │   │           └── mbedtls_md5_update                                                    138   0.07%
│   │   │   └── tinycrypt                                                                        4972   2.59%
│   │   │       └── lib                                                                          4972   2.59%
│   │   │           ├── include                                                                   176   0.09%
│   │   │           │   └── tinycrypt                                                             176   0.09%
│   │   │           │       └── ecc.h                                                             176   0.09%
│   │   │           │           └── curve_secp256r1                                               176   0.09%
│   │   │           └── source                                                                   4796   2.50%
│   │   │               ├── ecc.c                                                                2772   1.45%
│   │   │               │   ├── XYcZ_add                                                          206   0.11%
│   │   │               │   ├── apply_z                                                            62   0.03%
│   │   │               │   ├── cond_set                                                           18   0.01%
│   │   │               │   ├── double_jacobian_default                                           346   0.18%
│   │   │               │   ├── muladd                                                             44   0.02%
│   │   │               │   ├── uECC_secp256r1                                                      8   0.00%
│   │   │               │   ├── uECC_vli_add                                                       68   0.04%
│   │   │               │   ├── uECC_vli_bytesToNative                                             76   0.04%
│   │   │               │   ├── uECC_vli_clear                                                     20   0.01%
│   │   │               │   ├── uECC_vli_cmp_unsafe                                                52   0.03%
│   │   │               │   ├── uECC_vli_equal                                                     58   0.03%
│   │   │               │   ├── uECC_vli_isZero                                                    42   0.02%
│   │   │               │   ├── uECC_vli_mmod                                                     314   0.16%
│   │   │               │   ├── uECC_vli_modAdd                                                    46   0.02%
│   │   │               │   ├── uECC_vli_modInv                                                   306   0.16%
│   │   │               │   ├── uECC_vli_modMult                                                   36   0.02%
│   │   │               │   ├── uECC_vli_modMult_fast                                              32   0.02%
│   │   │               │   ├── uECC_vli_modSquare_fast                                            12   0.01%
│   │   │               │   ├── uECC_vli_modSub                                                    34   0.02%
│   │   │               │   ├── uECC_vli_mult                                                     188   0.10%
│   │   │               │   ├── uECC_vli_numBits                                                   52   0.03%
│   │   │               │   ├── uECC_vli_rshift1                                                   34   0.02%
│   │   │               │   ├── uECC_vli_set                                                       22   0.01%
│   │   │               │   ├── uECC_vli_sub                                                       68   0.04%
│   │   │               │   ├── uECC_vli_testBit                                                   18   0.01%
│   │   │               │   ├── vli_mmod_fast_secp256r1                                           428   0.22%
│   │   │               │   ├── vli_modInv_update                                                  60   0.03%
│   │   │               │   ├── vli_numDigits                                                      28   0.01%
│   │   │               │   └── x_side_default                                                     94   0.05%
│   │   │               ├── ecc_dsa.c                                                             916   0.48%
│   │   │               │   ├── bits2int                                                          164   0.09%
│   │   │               │   ├── smax                                                                8   0.00%
│   │   │               │   └── uECC_verify                                                       744   0.39%
│   │   │               ├── sha256.c                                                             1100   0.57%
│   │   │               │   ├── BigEndian                                                          42   0.02%
│   │   │               │   ├── compress                                                          408   0.21%
│   │   │               │   ├── k256                                                              256   0.13%
│   │   │               │   ├── tc_sha256_final                                                   216   0.11%
│   │   │               │   ├── tc_sha256_init                                                     92   0.05%
│   │   │               │   └── tc_sha256_update                                                   86   0.04%
│   │   │               └── utils.c                                                                 8   0.00%
│   │   │                   └── _set                                                                8   0.00%
│   │   └── hal                                                                                  8132   4.24%
│   │       ├── cmsis                                                                             176   0.09%
│   │       │   └── CMSIS                                                                         176   0.09%
│   │       │       └── Core                                                                      176   0.09%
│   │       │           └── Include                                                               176   0.09%
│   │       │               └── core_cm4.h                                                        176   0.09%
│   │       │                   ├── __NVIC_DisableIRQ                                              36   0.02%
│   │       │                   ├── __NVIC_EnableIRQ                                               28   0.01%
│   │       │                   ├── __NVIC_SetPriority                                             40   0.02%
│   │       │                   └── __NVIC_SystemReset                                             72   0.04%
│   │       └── nordic                                                                           7956   4.15%
│   │           └── nrfx                                                                         7956   4.15%
│   │               ├── drivers                                                                  5450   2.84%
│   │               │   ├── include                                                                18   0.01%
│   │               │   │   └── nrfx_power_clock.h                                                 18   0.01%
│   │               │   │       └── nrfx_power_clock_irq_init                                      18   0.01%
│   │               │   └── src                                                                  5432   2.83%
│   │               │       ├── nrfx_clock.c                                                      784   0.41%
│   │               │       │   ├── clock_initial_lfclksrc_get                                      4   0.00%
│   │               │       │   ├── clock_lfclksrc_tweak                                           44   0.02%
│   │               │       │   ├── clock_stop                                                    176   0.09%
│   │               │       │   ├── nrfx_clock_enable                                              68   0.04%
│   │               │       │   ├── nrfx_clock_init                                                80   0.04%
│   │               │       │   ├── nrfx_clock_start                                              232   0.12%
│   │               │       │   ├── nrfx_clock_stop                                                56   0.03%
│   │               │       │   └── nrfx_power_clock_irq_handler                                  124   0.06%
│   │               │       ├── nrfx_gpiote.c                                                    2262   1.18%
│   │               │       │   ├── call_handler                                                   44   0.02%
│   │               │       │   ├── channel_handler_get                                            32   0.02%
│   │               │       │   ├── find_handler                                                   44   0.02%
│   │               │       │   ├── get_initial_sense                                              52   0.03%
│   │               │       │   ├── gpiote_evt_handle                                              68   0.04%
│   │               │       │   ├── gpiote_polarity_to_trigger                                      2   0.00%
│   │               │       │   ├── gpiote_trigger_to_polarity                                      2   0.00%
│   │               │       │   ├── handler_in_use                                                 52   0.03%
│   │               │       │   ├── is_level                                                       10   0.01%
│   │               │       │   ├── latch_pending_read_and_check                                   38   0.02%
│   │               │       │   ├── m_cb                                                          124   0.06%
│   │               │       │   ├── next_sense_cond_call_handler                                  102   0.05%
│   │               │       │   ├── nrfx_gpiote_channel_alloc                                      16   0.01%
│   │               │       │   ├── nrfx_gpiote_channel_free                                       16   0.01%
│   │               │       │   ├── nrfx_gpiote_channel_get                                        84   0.04%
│   │               │       │   ├── nrfx_gpiote_global_callback_set                                12   0.01%
│   │               │       │   ├── nrfx_gpiote_init                                               84   0.04%
│   │               │       │   ├── nrfx_gpiote_input_configure                                   296   0.15%
│   │               │       │   ├── nrfx_gpiote_irq_handler                                        96   0.05%
│   │               │       │   ├── nrfx_gpiote_is_init                                            20   0.01%
│   │               │       │   ├── nrfx_gpiote_output_configure                                  212   0.11%
│   │               │       │   ├── nrfx_gpiote_pin_uninit                                         44   0.02%
│   │               │       │   ├── nrfx_gpiote_trigger_disable                                    68   0.04%
│   │               │       │   ├── nrfx_gpiote_trigger_enable                                    176   0.09%
│   │               │       │   ├── pin_handler_set                                               108   0.06%
│   │               │       │   ├── pin_handler_trigger_uninit                                     56   0.03%
│   │               │       │   ├── pin_has_trigger                                                24   0.01%
│   │               │       │   ├── pin_in_use                                                     20   0.01%
│   │               │       │   ├── pin_in_use_by_te                                               20   0.01%
│   │               │       │   ├── pin_is_input                                                   14   0.01%
│   │               │       │   ├── pin_is_output                                                  20   0.01%
│   │               │       │   ├── pin_is_task_output                                             30   0.02%
│   │               │       │   ├── pin_te_get                                                     16   0.01%
│   │               │       │   ├── port_event_handle                                             144   0.08%
│   │               │       │   └── release_handler                                               116   0.06%
│   │               │       ├── nrfx_ppi.c                                                         20   0.01%
│   │               │       │   ├── m_channels_allocated                                            4   0.00%
│   │               │       │   └── nrfx_ppi_channel_alloc                                         16   0.01%
│   │               │       ├── nrfx_twi_twim.c                                                   160   0.08%
│   │               │       │   └── nrfx_twi_twim_bus_recover                                     160   0.08%
│   │               │       └── nrfx_twim.c                                                      2206   1.15%
│   │               │           ├── nrfx_twim_0_irq_handler                                        20   0.01%
│   │               │           ├── nrfx_twim_disable                                             112   0.06%
│   │               │           ├── nrfx_twim_enable                                               88   0.05%
│   │               │           ├── nrfx_twim_init                                                188   0.10%
│   │               │           ├── nrfx_twim_xfer                                                168   0.09%
│   │               │           ├── twi_process_error                                              52   0.03%
│   │               │           ├── twim_irq_handler                                              516   0.27%
│   │               │           ├── twim_list_enable_handle                                        42   0.02%
│   │               │           ├── twim_pins_configure                                            86   0.04%
│   │               │           ├── twim_xfer                                                     804   0.42%
│   │               │           └── xfer_completeness_check                                       130   0.07%
│   │               ├── hal                                                                      1676   0.87%
│   │               │   ├── nrf_clock.h                                                           108   0.06%
│   │               │   │   └── nrf_clock_is_running                                              108   0.06%
│   │               │   ├── nrf_gpio.h                                                           1390   0.72%
│   │               │   │   ├── nrf_gpio_cfg                                                       56   0.03%
│   │               │   │   ├── nrf_gpio_cfg_default                                               30   0.02%
│   │               │   │   ├── nrf_gpio_cfg_sense_set                                             32   0.02%
│   │               │   │   ├── nrf_gpio_latches_read_and_clear                                    68   0.04%
│   │               │   │   ├── nrf_gpio_pin_clear                                                 56   0.03%
│   │               │   │   ├── nrf_gpio_pin_dir_get                                               32   0.02%
│   │               │   │   ├── nrf_gpio_pin_latch_clear                                           28   0.01%
│   │               │   │   ├── nrf_gpio_pin_port_decode                                          560   0.29%
│   │               │   │   ├── nrf_gpio_pin_present_check                                        180   0.09%
│   │               │   │   ├── nrf_gpio_pin_read                                                  60   0.03%
│   │               │   │   ├── nrf_gpio_pin_sense_get                                             32   0.02%
│   │               │   │   ├── nrf_gpio_pin_set                                                   56   0.03%
│   │               │   │   ├── nrf_gpio_pin_write                                                 16   0.01%
│   │               │   │   └── nrf_gpio_reconfigure                                              184   0.10%
│   │               │   ├── nrf_gpiote.h                                                          164   0.09%
│   │               │   │   ├── nrf_gpiote_event_configure                                         50   0.03%
│   │               │   │   ├── nrf_gpiote_in_event_get                                            52   0.03%
│   │               │   │   └── nrf_gpiote_task_configure                                          62   0.03%
│   │               │   └── nrf_power.h                                                            14   0.01%
│   │               │       └── nrf_power_system_off                                               14   0.01%
│   │               ├── helpers                                                                   148   0.08%
│   │               │   └── nrfx_flag32_allocator.c                                               148   0.08%
│   │               │       ├── nrfx_flag32_alloc                                                  80   0.04%
│   │               │       └── nrfx_flag32_free                                                   68   0.04%
│   │               └── mdk                                                                       682   0.36%
│   │                   ├── nrf52_erratas.h                                                       244   0.13%
│   │                   │   ├── nrf52_configuration_249                                            32   0.02%
│   │                   │   ├── nrf52_errata_103                                                   38   0.02%
│   │                   │   ├── nrf52_errata_115                                                   38   0.02%
│   │                   │   ├── nrf52_errata_120                                                   38   0.02%
│   │                   │   ├── nrf52_errata_136                                                   20   0.01%
│   │                   │   ├── nrf52_errata_36                                                    20   0.01%
│   │                   │   ├── nrf52_errata_66                                                    20   0.01%
│   │                   │   └── nrf52_errata_98                                                    38   0.02%
│   │                   ├── system_nrf52.c                                                        412   0.21%
│   │                   │   ├── SystemInit                                                        376   0.20%
│   │                   │   ├── nvmc_config                                                        20   0.01%
│   │                   │   └── nvmc_wait                                                          16   0.01%
│   │                   └── system_nrf52_approtect.h                                               26   0.01%
│   │                       └── nrf52_handle_approtect                                             26   0.01%
│   ├── nrf                                                                                       276   0.14%
│   │   ├── drivers                                                                               224   0.12%
│   │   │   ├── entropy                                                                           184   0.10%
│   │   │   │   └── entropy_cc3xx.c                                                               184   0.10%
│   │   │   │       ├── __devstate_dts_ord_98                                                       2   0.00%
│   │   │   │       ├── __init___device_dts_ord_98                                                  8   0.00%
│   │   │   │       ├── entropy_cc3xx_rng_api                                                       8   0.00%
│   │   │   │       ├── entropy_cc3xx_rng_get_entropy                                             144   0.08%
│   │   │   │       └── entropy_cc3xx_rng_init                                                     22   0.01%
│   │   │   └── hw_cc310                                                                           40   0.02%
│   │   │       └── hw_cc310.c                                                                     40   0.02%
│   │   │           ├── __init_hw_cc3xx_init                                                        8   0.00%
│   │   │           ├── __init_hw_cc3xx_init_internal                                               8   0.00%
│   │   │           ├── hw_cc3xx_init                                                              16   0.01%
│   │   │           └── hw_cc3xx_init_internal                                                      8   0.00%
│   │   └── lib                                                                                    52   0.03%
│   │       └── fatal_error                                                                        52   0.03%
│   │           └── fatal_error.c                                                                  52   0.03%
│   │               ├── k_sys_fatal_error_handler                                                  44   0.02%
│   │               └── log_const_fatal_error                                                       8   0.00%
│   └── nrfxlib                                                                                   716   0.37%
│       └── crypto                                                                                716   0.37%
│           └── nrf_cc310_platform                                                                716   0.37%
│               ├── include                                                                        56   0.03%
│               │   ├── nrf_cc3xx_platform_abort.h                                                 16   0.01%
│               │   │   └── nrf_cc3xx_platform_abort_init                                          16   0.01%
│               │   └── nrf_cc3xx_platform_mutex.h                                                 40   0.02%
│               │       └── nrf_cc3xx_platform_mutex_init                                          40   0.02%
│               └── src                                                                           660   0.34%
│                   ├── nrf_cc3xx_platform_abort_zephyr.c                                          16   0.01%
│                   │   ├── abort_function                                                          8   0.00%
│                   │   └── apis                                                                    8   0.00%
│                   └── nrf_cc3xx_platform_mutex_zephyr.c                                         644   0.34%
│                       ├── asym_mutex                                                              8   0.00%
│                       ├── asym_mutex_int                                                         20   0.01%
│                       ├── mutex_apis                                                             16   0.01%
│                       ├── mutex_flags_unknown                                                    80   0.04%
│                       ├── mutex_free_platform                                                    92   0.05%
│                       ├── mutex_init_platform                                                   136   0.07%
│                       ├── mutex_lock_platform                                                   100   0.05%
│                       ├── mutex_unlock_platform                                                  88   0.05%
│                       ├── mutexes                                                                20   0.01%
│                       ├── power_mutex                                                             8   0.00%
│                       ├── power_mutex_int                                                        20   0.01%
│                       ├── rng_mutex                                                               8   0.00%
│                       ├── rng_mutex_int                                                          20   0.01%
│                       ├── sym_mutex                                                               8   0.00%
│                       └── sym_mutex_int                                                          20   0.01%
└── ZEPHYR_BASE                                                                                119833  62.48%
    ├── arch                                                                                     3362   1.75%
    │   └── arm                                                                                  3362   1.75%
    │       └── core                                                                             3362   1.75%
    │           └── aarch32                                                                      3362   1.75%
    │               ├── cortex_m                                                                 2162   1.13%
    │               │   ├── fault.c                                                              1934   1.01%
    │               │   │   ├── bus_fault                                                         356   0.19%
    │               │   │   ├── debug_monitor                                                      40   0.02%
    │               │   │   ├── fault_handle                                                       74   0.04%
    │               │   │   ├── get_esf                                                            84   0.04%
    │               │   │   ├── hard_fault                                                        348   0.18%
    │               │   │   ├── mem_manage_fault                                                  416   0.22%
    │               │   │   ├── memory_fault_recoverable                                            4   0.00%
    │               │   │   ├── reserved_exception                                                 64   0.03%
    │               │   │   ├── usage_fault                                                       288   0.15%
    │               │   │   ├── z_arm_fault                                                       184   0.10%
    │               │   │   ├── z_arm_fault_init                                                   16   0.01%
    │               │   │   └── z_arm_is_synchronous_svc                                           60   0.03%
    │               │   ├── irq_init.c                                                             52   0.03%
    │               │   │   └── z_arm_interrupt_init                                               52   0.03%
    │               │   ├── scb.c                                                                 124   0.06%
    │               │   │   ├── z_arm_clear_arm_mpu_config                                         40   0.02%
    │               │   │   └── z_arm_init_arch_hw_at_boot                                         84   0.04%
    │               │   └── thread_abort.c                                                         52   0.03%
    │               │       └── z_impl_k_thread_abort                                              52   0.03%
    │               ├── fatal.c                                                                   184   0.10%
    │               │   ├── esf_dump                                                              148   0.08%
    │               │   ├── z_arm_fatal_error                                                      24   0.01%
    │               │   └── z_do_kernel_oops                                                       12   0.01%
    │               ├── irq_manage.c                                                              132   0.07%
    │               │   ├── arch_irq_disable                                                       10   0.01%
    │               │   ├── arch_irq_enable                                                        10   0.01%
    │               │   ├── arch_irq_is_enabled                                                    28   0.01%
    │               │   ├── z_arm_irq_priority_set                                                 72   0.04%
    │               │   └── z_irq_spurious                                                         12   0.01%
    │               ├── mpu                                                                       656   0.34%
    │               │   ├── arm_core_mpu.c                                                         48   0.03%
    │               │   │   ├── log_const_mpu                                                       8   0.00%
    │               │   │   ├── static_regions                                                     12   0.01%
    │               │   │   └── z_arm_configure_static_mpu_regions                                 28   0.01%
    │               │   ├── arm_mpu.c                                                             514   0.27%
    │               │   │   ├── arm_core_mpu_configure_static_mpu_regions                          68   0.04%
    │               │   │   ├── arm_core_mpu_disable                                               20   0.01%
    │               │   │   ├── arm_core_mpu_enable                                                24   0.01%
    │               │   │   ├── mpu_configure_region                                               62   0.03%
    │               │   │   ├── mpu_configure_regions                                             112   0.06%
    │               │   │   ├── region_allocate_and_init                                           56   0.03%
    │               │   │   └── z_arm_mpu_init                                                    172   0.09%
    │               │   └── arm_mpu_v7_internal.h                                                  94   0.05%
    │               │       ├── mpu_configure_static_mpu_regions                                   20   0.01%
    │               │       ├── mpu_partition_is_valid                                             34   0.02%
    │               │       └── region_init                                                        40   0.02%
    │               ├── nmi.c                                                                      12   0.01%
    │               │   └── z_arm_nmi                                                              12   0.01%
    │               ├── prep_c.c                                                                   56   0.03%
    │               │   └── z_arm_prep_c                                                           56   0.03%
    │               ├── swap.c                                                                     56   0.03%
    │               │   └── arch_swap                                                              56   0.03%
    │               └── thread.c                                                                  104   0.05%
    │                   ├── arch_new_thread                                                        68   0.04%
    │                   └── arch_switch_to_main_thread                                             36   0.02%
    ├── boards                                                                                     32   0.02%
    │   └── arm                                                                                    32   0.02%
    │       └── reel_board                                                                         32   0.02%
    │           └── board.c                                                                        32   0.02%
    │               ├── __init_board_reel_board_init                                                8   0.00%
    │               └── board_reel_board_init                                                      24   0.01%
    ├── drivers                                                                                  8874   4.63%
    │   ├── clock_control                                                                        1480   0.77%
    │   │   └── clock_control_nrf.c                                                              1480   0.77%
    │   │       ├── __devstate_dts_ord_57                                                           2   0.00%
    │   │       ├── __init___device_dts_ord_57                                                      8   0.00%
    │   │       ├── api_blocking_start                                                             60   0.03%
    │   │       ├── api_start                                                                      16   0.01%
    │   │       ├── api_stop                                                                       10   0.01%
    │   │       ├── async_start                                                                    56   0.03%
    │   │       ├── blocking_start_callback                                                        10   0.01%
    │   │       ├── clk_init                                                                       96   0.05%
    │   │       ├── clkstarted_handle                                                              36   0.02%
    │   │       ├── clock_control_api                                                              28   0.01%
    │   │       ├── clock_event_handler                                                           116   0.06%
    │   │       ├── config                                                                         24   0.01%
    │   │       ├── generic_hfclk_start                                                           112   0.06%
    │   │       ├── generic_hfclk_stop                                                             56   0.03%
    │   │       ├── get_hf_flags                                                                    8   0.00%
    │   │       ├── get_onoff_manager                                                               8   0.00%
    │   │       ├── get_status                                                                     56   0.03%
    │   │       ├── get_sub_config                                                                 12   0.01%
    │   │       ├── get_sub_data                                                                   14   0.01%
    │   │       ├── get_subsys                                                                     12   0.01%
    │   │       ├── hfclk_start                                                                    10   0.01%
    │   │       ├── hfclk_stop                                                                     10   0.01%
    │   │       ├── lfclk_spinwait                                                                204   0.11%
    │   │       ├── lfclk_start                                                                    10   0.01%
    │   │       ├── lfclk_stop                                                                     10   0.01%
    │   │       ├── log_const_clock_control                                                         8   0.00%
    │   │       ├── onoff_start                                                                    52   0.03%
    │   │       ├── onoff_started_callback                                                         16   0.01%
    │   │       ├── onoff_stop                                                                     32   0.02%
    │   │       ├── set_off_state                                                                  50   0.03%
    │   │       ├── set_on_state                                                                   38   0.02%
    │   │       ├── set_starting_state                                                             60   0.03%
    │   │       ├── stop                                                                           84   0.04%
    │   │       └── z_nrf_clock_control_lf_on                                                     156   0.08%
    │   ├── console                                                                               100   0.05%
    │   │   └── uart_console.c                                                                    100   0.05%
    │   │       ├── __init_uart_console_init                                                        8   0.00%
    │   │       ├── console_out                                                                    40   0.02%
    │   │       ├── uart_console_hook_install                                                      24   0.01%
    │   │       └── uart_console_init                                                              28   0.01%
    │   ├── entropy                                                                               880   0.46%
    │   │   └── entropy_nrf5.c                                                                    880   0.46%
    │   │       ├── __devstate_dts_ord_80                                                           2   0.00%
    │   │       ├── __init___device_dts_ord_80                                                      8   0.00%
    │   │       ├── entropy_nrf5_api_funcs                                                          8   0.00%
    │   │       ├── entropy_nrf5_get_entropy                                                      124   0.06%
    │   │       ├── entropy_nrf5_get_entropy_isr                                                  232   0.12%
    │   │       ├── entropy_nrf5_init                                                             156   0.08%
    │   │       ├── isr                                                                            72   0.04%
    │   │       ├── random_byte_get                                                                64   0.03%
    │   │       ├── rng_pool_get                                                                  160   0.08%
    │   │       ├── rng_pool_init                                                                  16   0.01%
    │   │       └── rng_pool_put                                                                   38   0.02%
    │   ├── gpio                                                                                 1024   0.53%
    │   │   └── gpio_nrfx.c                                                                      1024   0.53%
    │   │       ├── __devstate_dts_ord_13                                                           2   0.00%
    │   │       ├── __devstate_dts_ord_18                                                           2   0.00%
    │   │       ├── __init___device_dts_ord_13                                                      8   0.00%
    │   │       ├── __init___device_dts_ord_18                                                      8   0.00%
    │   │       ├── get_dev                                                                        28   0.01%
    │   │       ├── get_drive                                                                     134   0.07%
    │   │       ├── get_pull                                                                       24   0.01%
    │   │       ├── get_trigger                                                                    44   0.02%
    │   │       ├── gpio_nrfx_drv_api_funcs                                                        36   0.02%
    │   │       ├── gpio_nrfx_init                                                                 60   0.03%
    │   │       ├── gpio_nrfx_manage_callback                                                      12   0.01%
    │   │       ├── gpio_nrfx_p0_cfg                                                               16   0.01%
    │   │       ├── gpio_nrfx_p1_cfg                                                               16   0.01%
    │   │       ├── gpio_nrfx_pin_configure                                                       340   0.18%
    │   │       ├── gpio_nrfx_pin_interrupt_configure                                             176   0.09%
    │   │       ├── gpio_nrfx_port_clear_bits_raw                                                  12   0.01%
    │   │       ├── gpio_nrfx_port_get_raw                                                         14   0.01%
    │   │       ├── gpio_nrfx_port_set_bits_raw                                                    12   0.01%
    │   │       ├── gpio_nrfx_port_set_masked_raw                                                  24   0.01%
    │   │       ├── gpio_nrfx_port_toggle_bits                                                     26   0.01%
    │   │       └── nrfx_gpio_handler                                                              30   0.02%
    │   ├── i2c                                                                                  1160   0.60%
    │   │   ├── i2c_common.c                                                                        8   0.00%
    │   │   │   └── log_const_i2c                                                                   8   0.00%
    │   │   └── i2c_nrfx_twim.c                                                                  1152   0.60%
    │   │       ├── __devstate_dts_ord_108                                                          2   0.00%
    │   │       ├── __init___device_dts_ord_108                                                     8   0.00%
    │   │       ├── __pinctrl_dev_config__device_dts_ord_108                                       12   0.01%
    │   │       ├── __pinctrl_state_pins_0__device_dts_ord_108                                      8   0.00%
    │   │       ├── __pinctrl_states__device_dts_ord_108                                            8   0.00%
    │   │       ├── event_handler                                                                  64   0.03%
    │   │       ├── i2c_nrfx_twim_configure                                                        96   0.05%
    │   │       ├── i2c_nrfx_twim_driver_api                                                       24   0.01%
    │   │       ├── i2c_nrfx_twim_init                                                            104   0.05%
    │   │       ├── i2c_nrfx_twim_recover_bus                                                      64   0.03%
    │   │       ├── i2c_nrfx_twim_transfer                                                        648   0.34%
    │   │       ├── irq_connect0                                                                   14   0.01%
    │   │       ├── log_const_i2c_nrfx_twim                                                         8   0.00%
    │   │       ├── twim_0_data                                                                    56   0.03%
    │   │       └── twim_0z_config                                                                 36   0.02%
    │   ├── pinctrl                                                                               528   0.28%
    │   │   ├── common.c                                                                           50   0.03%
    │   │   │   └── pinctrl_lookup_state                                                           50   0.03%
    │   │   └── pinctrl_nrf.c                                                                     478   0.25%
    │   │       └── pinctrl_configure_pins                                                        478   0.25%
    │   ├── serial                                                                               2258   1.18%
    │   │   ├── uart_nrfx_uart.c                                                                  858   0.45%
    │   │   │   ├── __devstate_dts_ord_93                                                           2   0.00%
    │   │   │   ├── __init___device_dts_ord_93                                                      8   0.00%
    │   │   │   ├── __pinctrl_dev_config__device_dts_ord_93                                        12   0.01%
    │   │   │   ├── __pinctrl_state_pins_0__device_dts_ord_93                                       8   0.00%
    │   │   │   ├── __pinctrl_states__device_dts_ord_93                                             8   0.00%
    │   │   │   ├── baudrate_set                                                                  348   0.18%
    │   │   │   ├── event_txdrdy_check                                                             20   0.01%
    │   │   │   ├── event_txdrdy_clear                                                             20   0.01%
    │   │   │   ├── uart_nrfx_config_get                                                           16   0.01%
    │   │   │   ├── uart_nrfx_configure                                                           144   0.08%
    │   │   │   ├── uart_nrfx_err_check                                                            16   0.01%
    │   │   │   ├── uart_nrfx_init                                                                 64   0.03%
    │   │   │   ├── uart_nrfx_poll_in                                                              40   0.02%
    │   │   │   ├── uart_nrfx_poll_out                                                            120   0.06%
    │   │   │   ├── uart_nrfx_uart0_config                                                          4   0.00%
    │   │   │   ├── uart_nrfx_uart0_data                                                            8   0.00%
    │   │   │   └── uart_nrfx_uart_driver_api                                                      20   0.01%
    │   │   └── uart_nrfx_uarte.c                                                                1400   0.73%
    │   │       ├── __devstate_dts_ord_94                                                           2   0.00%
    │   │       ├── __init___device_dts_ord_94                                                      8   0.00%
    │   │       ├── __pinctrl_dev_config__device_dts_ord_94                                        12   0.01%
    │   │       ├── __pinctrl_state_pins_0__device_dts_ord_94                                       8   0.00%
    │   │       ├── __pinctrl_states__device_dts_ord_94                                             8   0.00%
    │   │       ├── baudrate_set                                                                  336   0.18%
    │   │       ├── endtx_isr                                                                      50   0.03%
    │   │       ├── endtx_stoptx_ppi_init                                                         104   0.05%
    │   │       ├── is_tx_ready                                                                    40   0.02%
    │   │       ├── log_const_uart_nrfx_uarte                                                       8   0.00%
    │   │       ├── tx_start                                                                       62   0.03%
    │   │       ├── uart_nrfx_uarte_driver_api                                                     20   0.01%
    │   │       ├── uarte_1_data                                                                   28   0.01%
    │   │       ├── uarte_1_init                                                                   30   0.02%
    │   │       ├── uarte_1z_config                                                                16   0.01%
    │   │       ├── uarte_enable                                                                   12   0.01%
    │   │       ├── uarte_instance_init                                                           164   0.09%
    │   │       ├── uarte_nrfx_config_get                                                          18   0.01%
    │   │       ├── uarte_nrfx_configure                                                          166   0.09%
    │   │       ├── uarte_nrfx_err_check                                                           14   0.01%
    │   │       ├── uarte_nrfx_isr_int                                                             82   0.04%
    │   │       ├── uarte_nrfx_poll_in                                                             44   0.02%
    │   │       ├── uarte_nrfx_poll_out                                                            92   0.05%
    │   │       └── wait_tx_ready                                                                  76   0.04%
    │   └── timer                                                                                1444   0.75%
    │       ├── nrf_rtc_timer.c                                                                  1442   0.75%
    │       │   ├── __init_sys_clock_driver_init                                                    8   0.00%
    │       │   ├── absolute_time_to_cc                                                             6   0.00%
    │       │   ├── channel_processing_check_and_clear                                             96   0.05%
    │       │   ├── compare_int_lock                                                               76   0.04%
    │       │   ├── compare_int_unlock                                                             96   0.05%
    │       │   ├── compare_set                                                                    50   0.03%
    │       │   ├── compare_set_nolocks                                                           144   0.08%
    │       │   ├── counter                                                                        12   0.01%
    │       │   ├── counter_sub                                                                     8   0.00%
    │       │   ├── event_check                                                                    26   0.01%
    │       │   ├── event_clear                                                                    24   0.01%
    │       │   ├── event_disable                                                                  20   0.01%
    │       │   ├── event_enable                                                                   20   0.01%
    │       │   ├── full_int_lock                                                                  18   0.01%
    │       │   ├── full_int_unlock                                                                10   0.01%
    │       │   ├── int_event_disable_rtc                                                          24   0.01%
    │       │   ├── process_channel                                                               124   0.06%
    │       │   ├── rtc_nrf_isr                                                                    68   0.04%
    │       │   ├── set_alarm                                                                     108   0.06%
    │       │   ├── set_comparator                                                                 20   0.01%
    │       │   ├── sys_clock_cycle_get_32                                                          8   0.00%
    │       │   ├── sys_clock_disable                                                              40   0.02%
    │       │   ├── sys_clock_driver_init                                                         152   0.08%
    │       │   ├── sys_clock_elapsed                                                              20   0.01%
    │       │   ├── sys_clock_set_timeout                                                         120   0.06%
    │       │   ├── sys_clock_timeout_handler                                                      80   0.04%
    │       │   └── z_nrf_rtc_timer_read                                                           64   0.03%
    │       └── sys_clock_init.c                                                                    2   0.00%
    │           └── sys_clock_idle_exit                                                             2   0.00%
    ├── include                                                                                  7482   3.90%
    │   └── zephyr                                                                               7482   3.90%
    │       ├── drivers                                                                           412   0.21%
    │       │   ├── entropy.h                                                                      56   0.03%
    │       │   │   └── z_impl_entropy_get_entropy                                                 56   0.03%
    │       │   ├── gpio                                                                          260   0.14%
    │       │   │   └── gpio_utils.h                                                              260   0.14%
    │       │   │       ├── gpio_fire_callbacks                                                   112   0.06%
    │       │   │       └── gpio_manage_callback                                                  148   0.08%
    │       │   └── pinctrl.h                                                                      96   0.05%
    │       │       └── pinctrl_apply_state                                                        96   0.05%
    │       ├── kernel.h                                                                          376   0.20%
    │       │   ├── k_msleep                                                                      220   0.11%
    │       │   └── k_uptime_get_32                                                               156   0.08%
    │       ├── logging                                                                           852   0.44%
    │       │   ├── log_backend.h                                                                 372   0.19%
    │       │   │   ├── log_backend_activate                                                       56   0.03%
    │       │   │   ├── log_backend_id_set                                                         44   0.02%
    │       │   │   ├── log_backend_init                                                           48   0.03%
    │       │   │   ├── log_backend_is_active                                                      48   0.03%
    │       │   │   ├── log_backend_is_ready                                                       52   0.03%
    │       │   │   ├── log_backend_msg_process                                                    76   0.04%
    │       │   │   └── log_backend_panic                                                          48   0.03%
    │       │   └── log_msg.h                                                                     480   0.25%
    │       │       └── z_log_msg_runtime_create                                                  480   0.25%
    │       ├── net                                                                              4840   2.52%
    │       │   ├── buf.h                                                                          18   0.01%
    │       │   │   └── net_buf_destroy                                                            18   0.01%
    │       │   ├── net_context.h                                                                1644   0.86%
    │       │   │   ├── net_context_get_family                                                    192   0.10%
    │       │   │   ├── net_context_get_iface                                                     256   0.13%
    │       │   │   ├── net_context_get_state                                                     128   0.07%
    │       │   │   ├── net_context_get_type                                                      128   0.07%
    │       │   │   ├── net_context_is_bound_to_iface                                             128   0.07%
    │       │   │   ├── net_context_is_closing                                                     64   0.03%
    │       │   │   ├── net_context_is_used                                                       128   0.07%
    │       │   │   ├── net_context_set_accepting                                                  84   0.04%
    │       │   │   ├── net_context_set_family                                                    160   0.08%
    │       │   │   ├── net_context_set_iface                                                     136   0.07%
    │       │   │   ├── net_context_set_state                                                     160   0.08%
    │       │   │   └── net_context_set_type                                                       80   0.04%
    │       │   ├── net_if.h                                                                     1128   0.59%
    │       │   │   ├── net_if_flag_clear                                                          64   0.03%
    │       │   │   ├── net_if_flag_set                                                            64   0.03%
    │       │   │   ├── net_if_flag_test_and_set                                                   64   0.03%
    │       │   │   ├── net_if_ipv6_maddr_is_joined                                               120   0.06%
    │       │   │   ├── net_if_ipv6_set_reachable_time                                             36   0.02%
    │       │   │   ├── net_if_is_admin_up                                                         64   0.03%
    │       │   │   ├── net_if_is_carrier_ok                                                       64   0.03%
    │       │   │   ├── net_if_is_dormant                                                          64   0.03%
    │       │   │   ├── net_if_is_up                                                              460   0.24%
    │       │   │   ├── net_if_oper_state                                                          60   0.03%
    │       │   │   └── net_if_oper_state_set                                                      68   0.04%
    │       │   ├── net_ip.h                                                                     1856   0.97%
    │       │   │   ├── net_ipv4_is_addr_bcast                                                    160   0.08%
    │       │   │   ├── net_ipv4_is_addr_mcast                                                    200   0.10%
    │       │   │   ├── net_ipv4_is_ll_addr                                                        44   0.02%
    │       │   │   ├── net_ipv4_is_my_addr                                                       128   0.07%
    │       │   │   ├── net_ipv6_addr_copy_raw                                                    180   0.09%
    │       │   │   ├── net_ipv6_addr_create_iid                                                  304   0.16%
    │       │   │   ├── net_ipv6_addr_create_ll_allnodes_mcast                                     88   0.05%
    │       │   │   ├── net_ipv6_addr_create_ll_allrouters_mcast                                   42   0.02%
    │       │   │   ├── net_ipv6_addr_create_solicited_node                                        88   0.05%
    │       │   │   ├── net_ipv6_is_addr_loopback                                                 240   0.13%
    │       │   │   ├── net_ipv6_is_addr_mcast_group                                               74   0.04%
    │       │   │   ├── net_ipv6_is_addr_mcast_link_all_nodes                                      44   0.02%
    │       │   │   ├── net_ipv6_is_addr_solicited_node                                            50   0.03%
    │       │   │   ├── net_ipv6_is_addr_unspecified                                              144   0.08%
    │       │   │   └── net_ipv6_is_prefix                                                         70   0.04%
    │       │   ├── net_linkaddr.h                                                                120   0.06%
    │       │   │   └── net_linkaddr_set                                                          120   0.06%
    │       │   └── net_pkt.h                                                                      74   0.04%
    │       │       ├── net_pkt_write_be16                                                         30   0.02%
    │       │       └── net_pkt_write_be32                                                         44   0.02%
    │       └── sys                                                                              1002   0.52%
    │           ├── atomic.h                                                                      378   0.20%
    │           │   ├── atomic_clear_bit                                                           40   0.02%
    │           │   ├── atomic_set_bit                                                             76   0.04%
    │           │   ├── atomic_test_and_clear_bit                                                  56   0.03%
    │           │   ├── atomic_test_and_set_bit                                                    50   0.03%
    │           │   └── atomic_test_bit                                                           156   0.08%
    │           ├── cbprintf.h                                                                     16   0.01%
    │           │   └── cbvprintf                                                                  16   0.01%
    │           ├── fdtable.h                                                                      32   0.02%
    │           │   └── z_fdtable_call_ioctl                                                       32   0.02%
    │           ├── notify.h                                                                       56   0.03%
    │           │   └── sys_notify_init_spinwait                                                   56   0.03%
    │           ├── sflist.h                                                                      106   0.06%
    │           │   ├── sys_sflist_append                                                          32   0.02%
    │           │   └── sys_sflist_insert                                                          74   0.04%
    │           └── slist.h                                                                       414   0.22%
    │               ├── sys_slist_find_and_remove                                                 224   0.12%
    │               └── sys_slist_remove                                                          190   0.10%
    ├── kernel                                                                                  19818  10.33%
    │   ├── banner.c                                                                                2   0.00%
    │   │   └── boot_banner                                                                         2   0.00%
    │   ├── condvar.c                                                                             324   0.17%
    │   │   ├── z_impl_k_condvar_init                                                               8   0.00%
    │   │   ├── z_impl_k_condvar_signal                                                           172   0.09%
    │   │   └── z_impl_k_condvar_wait                                                             144   0.08%
    │   ├── device.c                                                                              156   0.08%
    │   │   ├── z_device_is_ready                                                                  32   0.02%
    │   │   ├── z_device_state_init                                                                24   0.01%
    │   │   └── z_impl_device_get_binding                                                         100   0.05%
    │   ├── errno.c                                                                                16   0.01%
    │   │   ├── _k_neg_eagain                                                                       4   0.00%
    │   │   └── z_impl_z_errno                                                                     12   0.01%
    │   ├── fatal.c                                                                               312   0.16%
    │   │   ├── reason_to_str                                                                      64   0.03%
    │   │   ├── thread_name_get                                                                    32   0.02%
    │   │   └── z_fatal_error                                                                     216   0.11%
    │   ├── idle.c                                                                                116   0.06%
    │   │   ├── idle                                                                              104   0.05%
    │   │   └── z_pm_save_idle_exit                                                                12   0.01%
    │   ├── include                                                                               130   0.07%
    │   │   ├── kernel_offsets.h                                                                    2   0.00%
    │   │   │   └── _OffsetAbsSyms                                                                  2   0.00%
    │   │   └── ksched.h                                                                          128   0.07%
    │   │       ├── z_reschedule_unlocked                                                          24   0.01%
    │   │       └── z_sched_lock                                                                  104   0.05%
    │   ├── init.c                                                                                604   0.31%
    │   │   ├── bg_thread_main                                                                     52   0.03%
    │   │   ├── init_idle_thread                                                                   92   0.05%
    │   │   ├── log_const_os                                                                        8   0.00%
    │   │   ├── prepare_multithreading                                                             96   0.05%
    │   │   ├── switch_to_main_thread                                                              20   0.01%
    │   │   ├── z_bss_zero                                                                         24   0.01%
    │   │   ├── z_cstart                                                                          148   0.08%
    │   │   ├── z_early_memcpy                                                                      8   0.00%
    │   │   ├── z_early_memset                                                                      8   0.00%
    │   │   ├── z_init_cpu                                                                         64   0.03%
    │   │   └── z_sys_init_run_level                                                               84   0.04%
    │   ├── kheap.c                                                                               690   0.36%
    │   │   ├── __init_statics_init_pre                                                             8   0.00%
    │   │   ├── k_heap_aligned_alloc                                                              380   0.20%
    │   │   ├── k_heap_alloc                                                                       22   0.01%
    │   │   ├── k_heap_free                                                                       176   0.09%
    │   │   ├── k_heap_init                                                                        16   0.01%
    │   │   └── statics_init                                                                       88   0.05%
    │   ├── mem_slab.c                                                                            604   0.31%
    │   │   ├── __init_init_mem_slab_module                                                         8   0.00%
    │   │   ├── create_free_list                                                                   46   0.02%
    │   │   ├── init_mem_slab_module                                                               88   0.05%
    │   │   ├── k_mem_slab_alloc                                                                  228   0.12%
    │   │   ├── k_mem_slab_free                                                                   204   0.11%
    │   │   └── k_mem_slab_init                                                                    30   0.02%
    │   ├── mempool.c                                                                             210   0.11%
    │   │   ├── _system_heap                                                                       24   0.01%
    │   │   ├── k_free                                                                             18   0.01%
    │   │   ├── k_thread_system_pool_assign                                                        12   0.01%
    │   │   ├── z_heap_aligned_alloc                                                              112   0.06%
    │   │   └── z_thread_aligned_alloc                                                             44   0.02%
    │   ├── msg_q.c                                                                               720   0.38%
    │   │   ├── z_impl_k_msgq_get                                                                 368   0.19%
    │   │   └── z_impl_k_msgq_put                                                                 352   0.18%
    │   ├── mutex.c                                                                               926   0.48%
    │   │   ├── adjust_owner_prio                                                                  22   0.01%
    │   │   ├── new_prio_for_inheritance                                                           22   0.01%
    │   │   ├── z_impl_k_mutex_init                                                                14   0.01%
    │   │   ├── z_impl_k_mutex_lock                                                               556   0.29%
    │   │   └── z_impl_k_mutex_unlock                                                             312   0.16%
    │   ├── poll.c                                                                               2484   1.30%
    │   │   ├── add_event                                                                         140   0.07%
    │   │   ├── clear_event_registration                                                          260   0.14%
    │   │   ├── clear_event_registrations                                                         164   0.09%
    │   │   ├── is_condition_met                                                                  152   0.08%
    │   │   ├── k_poll_event_init                                                                 176   0.09%
    │   │   ├── poller_thread                                                                       8   0.00%
    │   │   ├── register_event                                                                    284   0.15%
    │   │   ├── register_events                                                                   248   0.13%
    │   │   ├── signal_poll_event                                                                  68   0.04%
    │   │   ├── signal_poller                                                                     156   0.08%
    │   │   ├── signal_triggered_work                                                              42   0.02%
    │   │   ├── z_handle_obj_poll_events                                                           30   0.02%
    │   │   ├── z_impl_k_poll                                                                     564   0.29%
    │   │   └── z_impl_k_poll_signal_raise                                                        192   0.10%
    │   ├── queue.c                                                                               806   0.42%
    │   │   ├── k_queue_append                                                                     24   0.01%
    │   │   ├── k_queue_prepend                                                                    22   0.01%
    │   │   ├── prepare_thread_to_run                                                              16   0.01%
    │   │   ├── queue_insert                                                                      260   0.14%
    │   │   ├── z_impl_k_queue_cancel_wait                                                        120   0.06%
    │   │   ├── z_impl_k_queue_get                                                                284   0.15%
    │   │   ├── z_impl_k_queue_init                                                                26   0.01%
    │   │   ├── z_impl_k_queue_peek_head                                                           12   0.01%
    │   │   ├── z_impl_k_queue_peek_tail                                                           12   0.01%
    │   │   └── z_queue_node_peek                                                                  30   0.02%
    │   ├── sched.c                                                                              5440   2.84%
    │   │   ├── add_thread_timeout                                                                 32   0.02%
    │   │   ├── add_to_waitq_locked                                                               132   0.07%
    │   │   ├── end_thread                                                                        100   0.05%
    │   │   ├── init_ready_q                                                                        8   0.00%
    │   │   ├── k_sched_lock                                                                      152   0.08%
    │   │   ├── k_sched_unlock                                                                    264   0.14%
    │   │   ├── move_thread_to_end_of_prio_q                                                      184   0.10%
    │   │   ├── pend_locked                                                                        24   0.01%
    │   │   ├── pended_on_thread                                                                   48   0.03%
    │   │   ├── ready_thread                                                                      164   0.09%
    │   │   ├── slice_timeout                                                                     112   0.06%
    │   │   ├── sliceable                                                                          76   0.04%
    │   │   ├── thread_active_elsewhere                                                             4   0.00%
    │   │   ├── unpend_all                                                                         42   0.02%
    │   │   ├── unpend_thread_no_timeout                                                           28   0.01%
    │   │   ├── unready_thread                                                                     56   0.03%
    │   │   ├── update_cache                                                                      124   0.06%
    │   │   ├── z_impl_k_sleep                                                                    136   0.07%
    │   │   ├── z_impl_k_thread_suspend                                                           228   0.12%
    │   │   ├── z_impl_k_yield                                                                    336   0.18%
    │   │   ├── z_impl_z_current_get                                                               12   0.01%
    │   │   ├── z_pend_curr                                                                       252   0.13%
    │   │   ├── z_priq_dumb_best                                                                   14   0.01%
    │   │   ├── z_priq_dumb_remove                                                                 68   0.04%
    │   │   ├── z_ready_thread                                                                    168   0.09%
    │   │   ├── z_reschedule                                                                      136   0.07%
    │   │   ├── z_reschedule_irqlock                                                               28   0.01%
    │   │   ├── z_reset_time_slice                                                                 80   0.04%
    │   │   ├── z_sched_init                                                                       16   0.01%
    │   │   ├── z_sched_prio_cmp                                                                   20   0.01%
    │   │   ├── z_sched_start                                                                     172   0.09%
    │   │   ├── z_sched_wait                                                                       40   0.02%
    │   │   ├── z_sched_wake                                                                      208   0.11%
    │   │   ├── z_sched_wake_thread                                                               196   0.10%
    │   │   ├── z_set_prio                                                                        336   0.18%
    │   │   ├── z_thread_abort                                                                    408   0.21%
    │   │   ├── z_thread_timeout                                                                   12   0.01%
    │   │   ├── z_tick_sleep                                                                      372   0.19%
    │   │   ├── z_time_slice                                                                      268   0.14%
    │   │   ├── z_unpend_all                                                                       32   0.02%
    │   │   ├── z_unpend_first_thread                                                             180   0.09%
    │   │   └── z_unpend_thread                                                                   172   0.09%
    │   ├── sem.c                                                                                 606   0.32%
    │   │   ├── z_impl_k_sem_give                                                                 144   0.08%
    │   │   ├── z_impl_k_sem_init                                                                  38   0.02%
    │   │   ├── z_impl_k_sem_reset                                                                132   0.07%
    │   │   └── z_impl_k_sem_take                                                                 292   0.15%
    │   ├── system_work_q.c                                                                        60   0.03%
    │   │   ├── __init_k_sys_work_q_init                                                            8   0.00%
    │   │   └── k_sys_work_q_init                                                                  52   0.03%
    │   ├── thread.c                                                                             1168   0.61%
    │   │   ├── k_is_in_isr                                                                        12   0.01%
    │   │   ├── k_thread_name_get                                                                   4   0.00%
    │   │   ├── schedule_new_thread                                                                28   0.01%
    │   │   ├── setup_thread_stack                                                                 42   0.02%
    │   │   ├── z_impl_k_thread_create                                                            124   0.06%
    │   │   ├── z_impl_k_thread_name_set                                                           36   0.02%
    │   │   ├── z_impl_k_thread_start                                                               8   0.00%
    │   │   ├── z_init_static_threads                                                             240   0.13%
    │   │   ├── z_init_thread_base                                                                 22   0.01%
    │   │   ├── z_setup_new_thread                                                                396   0.21%
    │   │   ├── z_spin_lock_set_owner                                                              16   0.01%
    │   │   ├── z_spin_lock_valid                                                                  32   0.02%
    │   │   ├── z_spin_unlock_valid                                                                32   0.02%
    │   │   └── z_thread_monitor_exit                                                             176   0.09%
    │   ├── timeout.c                                                                            1850   0.96%
    │   │   ├── elapsed                                                                            24   0.01%
    │   │   ├── first                                                                              20   0.01%
    │   │   ├── next                                                                               24   0.01%
    │   │   ├── next_timeout                                                                       58   0.03%
    │   │   ├── remove_timeout                                                                     46   0.02%
    │   │   ├── sys_clock_announce                                                                396   0.21%
    │   │   ├── sys_clock_tick_get                                                                176   0.09%
    │   │   ├── sys_clock_tick_get_32                                                               8   0.00%
    │   │   ├── sys_clock_timeout_end_calc                                                         90   0.05%
    │   │   ├── timeout_list                                                                        8   0.00%
    │   │   ├── timeout_rem                                                                        60   0.03%
    │   │   ├── z_abort_timeout                                                                   176   0.09%
    │   │   ├── z_add_timeout                                                                     412   0.21%
    │   │   ├── z_get_next_timeout_expiry                                                         160   0.08%
    │   │   ├── z_impl_k_busy_wait                                                                 12   0.01%
    │   │   ├── z_impl_k_uptime_ticks                                                               8   0.00%
    │   │   └── z_timeout_remaining                                                               172   0.09%
    │   ├── work.c                                                                               2542   1.33%
    │   │   ├── cancel_async_locked                                                                42   0.02%
    │   │   ├── cancel_delayable_async_locked                                                      16   0.01%
    │   │   ├── finalize_cancel_locked                                                             96   0.05%
    │   │   ├── k_work_cancel_delayable                                                           192   0.10%
    │   │   ├── k_work_delayable_busy_get                                                         152   0.08%
    │   │   ├── k_work_init_delayable                                                              96   0.05%
    │   │   ├── k_work_queue_start                                                                244   0.13%
    │   │   ├── k_work_reschedule                                                                  16   0.01%
    │   │   ├── k_work_reschedule_for_queue                                                       216   0.11%
    │   │   ├── k_work_schedule_for_queue                                                         216   0.11%
    │   │   ├── notify_queue_locked                                                                20   0.01%
    │   │   ├── queue_remove_locked                                                                26   0.01%
    │   │   ├── queue_submit_locked                                                               124   0.06%
    │   │   ├── schedule_for_queue_locked                                                          52   0.03%
    │   │   ├── submit_to_queue_locked                                                            136   0.07%
    │   │   ├── unschedule_locked                                                                  34   0.02%
    │   │   ├── work_queue_main                                                                   476   0.25%
    │   │   ├── work_timeout                                                                      188   0.10%
    │   │   └── z_work_submit_to_queue                                                            200   0.10%
    │   └── xip.c                                                                                  52   0.03%
    │       └── z_data_copy                                                                        52   0.03%
    ├── lib                                                                                      8600   4.48%
    │   ├── libc                                                                                  186   0.10%
    │   │   └── newlib                                                                            186   0.10%
    │   │       └── libc-hooks.c                                                                  186   0.10%
    │   │           ├── __init_malloc_prepare                                                       8   0.00%
    │   │           ├── __lock___malloc_recursive_mutex                                            20   0.01%
    │   │           ├── __stdout_hook_install                                                      12   0.01%
    │   │           ├── _stdout_hook                                                                4   0.00%
    │   │           ├── _stdout_hook_default                                                        6   0.00%
    │   │           ├── _write                                                                     12   0.01%
    │   │           ├── malloc_prepare                                                             72   0.04%
    │   │           └── z_impl_zephyr_write_stdout                                                 52   0.03%
    │   └── os                                                                                   8414   4.39%
    │       ├── assert.c                                                                           42   0.02%
    │       │   ├── assert_post_action                                                             14   0.01%
    │       │   └── assert_print                                                                   28   0.01%
    │       ├── cbprintf_complete.c                                                              2758   1.44%
    │       │   ├── conversion_radix                                                               42   0.02%
    │       │   ├── encode_uint                                                                   172   0.09%
    │       │   ├── extract_conversion                                                             68   0.04%
    │       │   ├── extract_decimal                                                                44   0.02%
    │       │   ├── extract_flags                                                                 196   0.10%
    │       │   ├── extract_length                                                                206   0.11%
    │       │   ├── extract_prec                                                                  100   0.05%
    │       │   ├── extract_specifier                                                             290   0.15%
    │       │   ├── extract_width                                                                  94   0.05%
    │       │   ├── outs                                                                           52   0.03%
    │       │   ├── store_count                                                                    62   0.03%
    │       │   └── z_cbvprintf_impl                                                             1432   0.75%
    │       ├── cbprintf_packaged.c                                                              1442   0.75%
    │       │   ├── cbpprintf_external                                                             96   0.05%
    │       │   ├── cbprintf_via_va_list                                                           14   0.01%
    │       │   ├── cbvprintf_package                                                            1324   0.69%
    │       │   └── log_const_cbprintf_package                                                      8   0.00%
    │       ├── fdtable.c                                                                         448   0.23%
    │       │   ├── _check_fd                                                                      60   0.03%
    │       │   ├── _find_fd_entry                                                                 48   0.03%
    │       │   ├── fdtable_lock                                                                   20   0.01%
    │       │   ├── z_fd_ref                                                                       36   0.02%
    │       │   ├── z_fd_unref                                                                     88   0.05%
    │       │   ├── z_finalize_fd                                                                  56   0.03%
    │       │   ├── z_free_fd                                                                       8   0.00%
    │       │   ├── z_get_fd_obj_and_vtable                                                        56   0.03%
    │       │   └── z_reserve_fd                                                                   76   0.04%
    │       ├── heap.c                                                                           1390   0.72%
    │       │   ├── alloc_chunk                                                                   118   0.06%
    │       │   ├── chunk_mem                                                                       8   0.00%
    │       │   ├── free_chunk                                                                     98   0.05%
    │       │   ├── free_list_add                                                                  24   0.01%
    │       │   ├── free_list_add_bidx                                                             78   0.04%
    │       │   ├── free_list_remove                                                               24   0.01%
    │       │   ├── free_list_remove_bidx                                                          62   0.03%
    │       │   ├── mem_to_chunkid                                                                  8   0.00%
    │       │   ├── merge_chunks                                                                   52   0.03%
    │       │   ├── split_chunks                                                                   58   0.03%
    │       │   ├── sys_heap_aligned_alloc                                                        292   0.15%
    │       │   ├── sys_heap_alloc                                                                100   0.05%
    │       │   ├── sys_heap_free                                                                 152   0.08%
    │       │   └── sys_heap_init                                                                 316   0.16%
    │       ├── notify.c                                                                          150   0.08%
    │       │   ├── sys_notify_finalize                                                            88   0.05%
    │       │   └── sys_notify_validate                                                            62   0.03%
    │       ├── onoff.c                                                                          1936   1.01%
    │       │   ├── notify_all                                                                     46   0.02%
    │       │   ├── notify_monitors                                                                68   0.04%
    │       │   ├── notify_one                                                                     38   0.02%
    │       │   ├── onoff_manager_init                                                             56   0.03%
    │       │   ├── onoff_request                                                                 360   0.19%
    │       │   ├── process_complete                                                              232   0.12%
    │       │   ├── process_event                                                                 928   0.48%
    │       │   ├── process_recheck                                                                50   0.03%
    │       │   ├── set_state                                                                      16   0.01%
    │       │   ├── transition_complete                                                           100   0.05%
    │       │   └── validate_args                                                                  42   0.02%
    │       ├── printk.c                                                                          180   0.09%
    │       │   ├── __printk_hook_install                                                          12   0.01%
    │       │   ├── _char_out                                                                       4   0.00%
    │       │   ├── arch_printk_char_out                                                            4   0.00%
    │       │   ├── printk                                                                         28   0.01%
    │       │   ├── snprintk                                                                       28   0.01%
    │       │   ├── str_out                                                                        48   0.03%
    │       │   ├── vprintk                                                                         8   0.00%
    │       │   └── vsnprintk                                                                      48   0.03%
    │       ├── reboot.c                                                                           48   0.03%
    │       │   └── sys_reboot                                                                     48   0.03%
    │       └── thread_entry.c                                                                     20   0.01%
    │           └── z_thread_entry                                                                 20   0.01%
    ├── modules                                                                                    58   0.03%
    │   ├── hal_nordic                                                                             46   0.02%
    │   │   └── nrfx                                                                               46   0.02%
    │   │       ├── nrfx_glue.c                                                                    14   0.01%
    │   │       │   ├── nrfx_busy_wait                                                              8   0.00%
    │   │       │   └── nrfx_isr                                                                    6   0.00%
    │   │       └── nrfx_log.h                                                                     32   0.02%
    │   │           ├── log_const_NRFX_CLOCK                                                        8   0.00%
    │   │           ├── log_const_NRFX_GPIOTE                                                       8   0.00%
    │   │           ├── log_const_NRFX_PPI                                                          8   0.00%
    │   │           └── log_const_NRFX_TWIM                                                         8   0.00%
    │   └── mbedtls                                                                                12   0.01%
    │       └── zephyr_init.c                                                                      12   0.01%
    │           ├── __init__mbedtls_init                                                            8   0.00%
    │           └── _mbedtls_init                                                                   4   0.00%
    ├── soc                                                                                       156   0.08%
    │   └── arm                                                                                   156   0.08%
    │       ├── common                                                                             24   0.01%
    │       │   └── cortex_m                                                                       24   0.01%
    │       │       └── arm_mpu_regions.c                                                          24   0.01%
    │       │           └── mpu_regions                                                            24   0.01%
    │       └── nordic_nrf                                                                        132   0.07%
    │           └── nrf52                                                                         132   0.07%
    │               ├── power.c                                                                    28   0.01%
    │               │   ├── pm_state_exit_post_ops                                                 12   0.01%
    │               │   └── pm_state_set                                                           16   0.01%
    │               └── soc.c                                                                     104   0.05%
    │                   ├── __init_nordicsemi_nrf52_init                                            8   0.00%
    │                   ├── arch_busy_wait                                                         24   0.01%
    │                   ├── log_const_soc                                                           8   0.00%
    │                   ├── nordicsemi_nrf52_init                                                  48   0.03%
    │                   └── sys_arch_reboot                                                        16   0.01%
    └── subsys                                                                                  71451  37.25%
        ├── debug                                                                                  61   0.03%
        │   └── thread_info.c                                                                      61   0.03%
        │       ├── _kernel_thread_info_num_offsets                                                 4   0.00%
        │       ├── _kernel_thread_info_offsets                                                    56   0.03%
        │       └── _kernel_thread_info_size_t_size                                                 1   0.00%
        ├── logging                                                                              2778   1.45%
        │   ├── backends                                                                          224   0.12%
        │   │   └── log_backend_uart.c                                                            224   0.12%
        │   │       ├── char_out                                                                   36   0.02%
        │   │       ├── format_set                                                                 12   0.01%
        │   │       ├── log_backend_uart                                                           16   0.01%
        │   │       ├── log_backend_uart_api                                                       28   0.01%
        │   │       ├── log_backend_uart_init                                                      52   0.03%
        │   │       ├── log_const_log_uart                                                          8   0.00%
        │   │       ├── log_output_uart                                                            16   0.01%
        │   │       ├── panic                                                                      24   0.01%
        │   │       └── process                                                                    32   0.02%
        │   ├── log_core.c                                                                        934   0.49%
        │   │   ├── __init_enable_logger                                                            8   0.00%
        │   │   ├── activate_foreach_backend                                                       80   0.04%
        │   │   ├── default_get_timestamp                                                           8   0.00%
        │   │   ├── dummy_timestamp                                                                 4   0.00%
        │   │   ├── enable_logger                                                                  14   0.01%
        │   │   ├── format_table                                                                   16   0.01%
        │   │   ├── log_buffer                                                                     68   0.04%
        │   │   ├── log_const_log                                                                   8   0.00%
        │   │   ├── log_core_init                                                                  44   0.02%
        │   │   ├── log_format_func_t_get                                                          12   0.01%
        │   │   ├── log_msg_ptr                                                                     4   0.00%
        │   │   ├── log_set_timestamp_func                                                         36   0.02%
        │   │   ├── msg_commit                                                                     10   0.01%
        │   │   ├── msg_filter_check                                                                4   0.00%
        │   │   ├── msg_process                                                                   112   0.06%
        │   │   ├── timestamp_func                                                                  4   0.00%
        │   │   ├── z_impl_log_panic                                                              124   0.06%
        │   │   ├── z_log_dropped                                                                  64   0.03%
        │   │   ├── z_log_get_tag                                                                   4   0.00%
        │   │   ├── z_log_init                                                                    236   0.12%
        │   │   ├── z_log_msg_commit                                                               32   0.02%
        │   │   ├── z_log_notify_backend_enabled                                                   12   0.01%
        │   │   └── z_log_vprintk                                                                  30   0.02%
        │   ├── log_mgmt.c                                                                        100   0.05%
        │   │   ├── log_backend_enable                                                             44   0.02%
        │   │   ├── log_const_log_mgmt                                                              8   0.00%
        │   │   ├── log_source_name_get                                                            28   0.01%
        │   │   └── log_src_cnt_get                                                                20   0.01%
        │   ├── log_msg.c                                                                         258   0.13%
        │   │   ├── z_impl_z_log_msg_runtime_vcreate                                              212   0.11%
        │   │   └── z_log_msg_finalize                                                             46   0.02%
        │   └── log_output.c                                                                     1262   0.66%
        │       ├── buffer_write                                                                   26   0.01%
        │       ├── color_postfix                                                                  12   0.01%
        │       ├── color_prefix                                                                   12   0.01%
        │       ├── color_print                                                                    44   0.02%
        │       ├── colors                                                                         20   0.01%
        │       ├── cr_out_func                                                                    30   0.02%
        │       ├── hexdump_line_print                                                            196   0.10%
        │       ├── ids_print                                                                     108   0.06%
        │       ├── log_msg_hexdump                                                                54   0.03%
        │       ├── log_output_flush                                                               26   0.01%
        │       ├── log_output_msg_process                                                        108   0.06%
        │       ├── log_output_process                                                            172   0.09%
        │       ├── log_output_timestamp_freq_set                                                  44   0.02%
        │       ├── newline_print                                                                  40   0.02%
        │       ├── out_func                                                                       30   0.02%
        │       ├── postfix_print                                                                  24   0.01%
        │       ├── prefix_print                                                                  116   0.06%
        │       ├── print_formatted                                                                40   0.02%
        │       ├── severity                                                                       20   0.01%
        │       └── timestamp_print                                                               140   0.07%
        ├── net                                                                                 67506  35.20%
        │   ├── buf.c                                                                            1324   0.69%
        │   │   ├── data_alloc                                                                     40   0.02%
        │   │   ├── data_unref                                                                     34   0.02%
        │   │   ├── fixed_data_alloc                                                               44   0.02%
        │   │   ├── fixed_data_unref                                                                2   0.00%
        │   │   ├── log_const_net_buf                                                               8   0.00%
        │   │   ├── net_buf_alloc_fixed                                                            14   0.01%
        │   │   ├── net_buf_alloc_len                                                             520   0.27%
        │   │   ├── net_buf_frag_add                                                               72   0.04%
        │   │   ├── net_buf_frag_insert                                                            96   0.05%
        │   │   ├── net_buf_frag_last                                                              56   0.03%
        │   │   ├── net_buf_id                                                                     30   0.02%
        │   │   ├── net_buf_linearize                                                              88   0.05%
        │   │   ├── net_buf_pool_get                                                               16   0.01%
        │   │   ├── net_buf_ref                                                                    52   0.03%
        │   │   ├── net_buf_reset                                                                  80   0.04%
        │   │   ├── net_buf_unref                                                                 108   0.06%
        │   │   ├── pool_get_uninit                                                                40   0.02%
        │   │   └── pool_id                                                                        24   0.01%
        │   ├── buf_simple.c                                                                      232   0.12%
        │   │   ├── log_const_net_buf_simple                                                        8   0.00%
        │   │   ├── net_buf_simple_add                                                             64   0.03%
        │   │   ├── net_buf_simple_headroom                                                         8   0.00%
        │   │   ├── net_buf_simple_max_len                                                         14   0.01%
        │   │   ├── net_buf_simple_pull                                                            60   0.03%
        │   │   ├── net_buf_simple_pull_mem                                                        60   0.03%
        │   │   └── net_buf_simple_tailroom                                                        18   0.01%
        │   ├── ip                                                                              57572  30.02%
        │   │   ├── connection.c                                                                 1862   0.97%
        │   │   │   ├── conn_addr_cmp                                                             130   0.07%
        │   │   │   ├── conn_are_endpoints_valid                                                  108   0.06%
        │   │   │   ├── conn_find_handler                                                         320   0.17%
        │   │   │   ├── conn_get_unused                                                            72   0.04%
        │   │   │   ├── conn_lock                                                                  20   0.01%
        │   │   │   ├── conn_send_icmp_error                                                       34   0.02%
        │   │   │   ├── conn_set_unused                                                            60   0.03%
        │   │   │   ├── conn_set_used                                                              64   0.03%
        │   │   │   ├── log_const_net_conn                                                          8   0.00%
        │   │   │   ├── net_conn_init                                                              80   0.04%
        │   │   │   ├── net_conn_input                                                            540   0.28%
        │   │   │   ├── net_conn_register                                                         326   0.17%
        │   │   │   └── net_conn_unregister                                                       100   0.05%
        │   │   ├── dhcpv4.c                                                                     3338   1.74%
        │   │   │   ├── dhcpv4_add_cookie                                                          24   0.01%
        │   │   │   ├── dhcpv4_add_end                                                             34   0.02%
        │   │   │   ├── dhcpv4_add_file                                                            20   0.01%
        │   │   │   ├── dhcpv4_add_msg_type                                                        26   0.01%
        │   │   │   ├── dhcpv4_add_option_length_value                                             70   0.04%
        │   │   │   ├── dhcpv4_add_req_ipaddr                                                      14   0.01%
        │   │   │   ├── dhcpv4_add_req_options                                                     20   0.01%
        │   │   │   ├── dhcpv4_add_server_id                                                       14   0.01%
        │   │   │   ├── dhcpv4_add_sname                                                           20   0.01%
        │   │   │   ├── dhcpv4_create_message                                                     368   0.19%
        │   │   │   ├── dhcpv4_enter_bound                                                         84   0.04%
        │   │   │   ├── dhcpv4_enter_requesting                                                    24   0.01%
        │   │   │   ├── dhcpv4_enter_selecting                                                     24   0.01%
        │   │   │   ├── dhcpv4_get_timeleft                                                        62   0.03%
        │   │   │   ├── dhcpv4_handle_msg_ack                                                      52   0.03%
        │   │   │   ├── dhcpv4_handle_msg_nak                                                      60   0.03%
        │   │   │   ├── dhcpv4_handle_reply                                                        44   0.02%
        │   │   │   ├── dhcpv4_iface_event_handler                                                108   0.06%
        │   │   │   ├── dhcpv4_immediate_timeout                                                   84   0.04%
        │   │   │   ├── dhcpv4_manage_timers                                                      212   0.11%
        │   │   │   ├── dhcpv4_parse_options                                                      604   0.31%
        │   │   │   ├── dhcpv4_rebinding_timeleft                                                  38   0.02%
        │   │   │   ├── dhcpv4_renewal_timeleft                                                    38   0.02%
        │   │   │   ├── dhcpv4_request_timeleft                                                    24   0.01%
        │   │   │   ├── dhcpv4_send_discover                                                       88   0.05%
        │   │   │   ├── dhcpv4_send_request                                                       192   0.10%
        │   │   │   ├── dhcpv4_set_timeout                                                         76   0.04%
        │   │   │   ├── dhcpv4_start_internal                                                     156   0.08%
        │   │   │   ├── dhcpv4_timeout                                                            208   0.11%
        │   │   │   ├── dhcpv4_update_message_timeout                                              72   0.04%
        │   │   │   ├── lock                                                                       20   0.01%
        │   │   │   ├── log_const_net_dhcpv4                                                        8   0.00%
        │   │   │   ├── magic_cookie                                                                4   0.00%
        │   │   │   ├── net_dhcpv4_init                                                            96   0.05%
        │   │   │   ├── net_dhcpv4_input                                                          284   0.15%
        │   │   │   ├── net_dhcpv4_start                                                           10   0.01%
        │   │   │   └── net_dhcpv4_state_name                                                      56   0.03%
        │   │   ├── icmpv4.c                                                                      854   0.45%
        │   │   │   ├── echo_request_handler                                                       12   0.01%
        │   │   │   ├── icmpv4_create                                                              54   0.03%
        │   │   │   ├── icmpv4_handle_echo_request                                                248   0.13%
        │   │   │   ├── log_const_net_icmpv4                                                        8   0.00%
        │   │   │   ├── net_icmpv4_finalize                                                        68   0.04%
        │   │   │   ├── net_icmpv4_init                                                            16   0.01%
        │   │   │   ├── net_icmpv4_input                                                          152   0.08%
        │   │   │   ├── net_icmpv4_register_handler                                                24   0.01%
        │   │   │   └── net_icmpv4_send_error                                                     272   0.14%
        │   │   ├── icmpv6.c                                                                      952   0.50%
        │   │   │   ├── echo_request_handler                                                       12   0.01%
        │   │   │   ├── icmpv6_handle_echo_request                                                214   0.11%
        │   │   │   ├── log_const_net_icmpv6                                                        8   0.00%
        │   │   │   ├── net_icmpv6_create                                                          54   0.03%
        │   │   │   ├── net_icmpv6_finalize                                                        68   0.04%
        │   │   │   ├── net_icmpv6_init                                                            16   0.01%
        │   │   │   ├── net_icmpv6_input                                                          136   0.07%
        │   │   │   ├── net_icmpv6_register_handler                                                24   0.01%
        │   │   │   └── net_icmpv6_send_error                                                     420   0.22%
        │   │   ├── ipv4.c                                                                        806   0.42%
        │   │   │   ├── log_const_net_ipv4                                                          8   0.00%
        │   │   │   ├── net_ipv4_create                                                            40   0.02%
        │   │   │   ├── net_ipv4_create_full                                                      148   0.08%
        │   │   │   ├── net_ipv4_finalize                                                         164   0.09%
        │   │   │   ├── net_ipv4_init                                                               2   0.00%
        │   │   │   └── net_ipv4_input                                                            444   0.23%
        │   │   ├── ipv6.c                                                                       1542   0.80%
        │   │   │   ├── extension_to_bitmap                                                        50   0.03%
        │   │   │   ├── ipv6_drop_on_unknown_option                                                46   0.02%
        │   │   │   ├── ipv6_handle_ext_hdr_options                                               230   0.12%
        │   │   │   ├── ipv6_route_packet                                                         106   0.06%
        │   │   │   ├── log_const_net_ipv6                                                          8   0.00%
        │   │   │   ├── net_ipv6_create                                                           132   0.07%
        │   │   │   ├── net_ipv6_finalize                                                         192   0.10%
        │   │   │   ├── net_ipv6_init                                                              12   0.01%
        │   │   │   └── net_ipv6_input                                                            766   0.40%
        │   │   ├── ipv6_mld.c                                                                   1058   0.55%
        │   │   │   ├── handle_mld_query                                                          176   0.09%
        │   │   │   ├── mld_create                                                                102   0.05%
        │   │   │   ├── mld_create_packet                                                         262   0.14%
        │   │   │   ├── mld_query_input_handler                                                    12   0.01%
        │   │   │   ├── mld_send                                                                   42   0.02%
        │   │   │   ├── mld_send_generic                                                           92   0.05%
        │   │   │   ├── net_ipv6_mld_init                                                          16   0.01%
        │   │   │   ├── net_ipv6_mld_join                                                         120   0.06%
        │   │   │   └── send_mld_report                                                           236   0.12%
        │   │   ├── ipv6_nbr.c                                                                   7018   3.66%
        │   │   │   ├── add_nbr                                                                    64   0.03%
        │   │   │   ├── check_route                                                                60   0.03%
        │   │   │   ├── dbg_update_neighbor_lladdr                                                 44   0.02%
        │   │   │   ├── dbg_update_neighbor_lladdr_raw                                             30   0.02%
        │   │   │   ├── handle_na_input                                                           284   0.15%
        │   │   │   ├── handle_na_neighbor                                                        524   0.27%
        │   │   │   ├── handle_ns_input                                                           486   0.25%
        │   │   │   ├── handle_prefix_autonomous                                                  174   0.09%
        │   │   │   ├── handle_prefix_onlink                                                      114   0.06%
        │   │   │   ├── handle_ra_input                                                           692   0.36%
        │   │   │   ├── handle_ra_neighbor                                                         56   0.03%
        │   │   │   ├── handle_ra_prefix                                                          172   0.09%
        │   │   │   ├── handle_ra_rdnss                                                           140   0.07%
        │   │   │   ├── handle_ra_route_info                                                      170   0.09%
        │   │   │   ├── ipv6_nbr_set_state                                                        144   0.08%
        │   │   │   ├── ipv6_nd_reachable_timeout                                                 380   0.20%
        │   │   │   ├── ipv6_nd_remove_old_stale_nbr                                              140   0.07%
        │   │   │   ├── ipv6_nd_restart_reachable_timer                                           196   0.10%
        │   │   │   ├── ipv6_ns_reply_timeout                                                     256   0.13%
        │   │   │   ├── na_input_handler                                                           12   0.01%
        │   │   │   ├── nbr_clear_ns_pending                                                       26   0.01%
        │   │   │   ├── nbr_free                                                                   42   0.02%
        │   │   │   ├── nbr_init                                                                   94   0.05%
        │   │   │   ├── nbr_lookup                                                                 76   0.04%
        │   │   │   ├── nbr_new                                                                    48   0.03%
        │   │   │   ├── net_ipv6_nbr_add                                                          172   0.09%
        │   │   │   ├── net_ipv6_nbr_init                                                          84   0.04%
        │   │   │   ├── net_ipv6_nbr_lookup                                                        20   0.01%
        │   │   │   ├── net_ipv6_nbr_rm                                                            64   0.03%
        │   │   │   ├── net_ipv6_nbr_set_reachable_timer                                           72   0.04%
        │   │   │   ├── net_ipv6_prepare_for_send                                                 372   0.19%
        │   │   │   ├── net_ipv6_send_na                                                          226   0.12%
        │   │   │   ├── net_ipv6_send_ns                                                          476   0.25%
        │   │   │   ├── net_ipv6_send_rs                                                          192   0.10%
        │   │   │   ├── net_ipv6_start_dad                                                         28   0.01%
        │   │   │   ├── net_ipv6_start_rs                                                           8   0.00%
        │   │   │   ├── net_neighbor                                                               12   0.01%
        │   │   │   ├── net_neighbor_data_remove                                                    2   0.00%
        │   │   │   ├── net_neighbor_pool                                                         672   0.35%
        │   │   │   ├── net_neighbor_table_clear                                                    2   0.00%
        │   │   │   ├── ns_input_handler                                                           12   0.01%
        │   │   │   ├── ra_input_handler                                                           12   0.01%
        │   │   │   ├── read_llao                                                                  76   0.04%
        │   │   │   ├── remaining_lifetime                                                         20   0.01%
        │   │   │   └── set_llao                                                                   72   0.04%
        │   │   ├── nbr.c                                                                         562   0.29%
        │   │   │   ├── get_nbr                                                                    64   0.03%
        │   │   │   ├── log_const_net_nbr                                                           8   0.00%
        │   │   │   ├── net_nbr_get                                                                46   0.02%
        │   │   │   ├── net_nbr_get_lladdr                                                         72   0.04%
        │   │   │   ├── net_nbr_link                                                              188   0.10%
        │   │   │   ├── net_nbr_ref                                                                 8   0.00%
        │   │   │   ├── net_nbr_unlink                                                            156   0.08%
        │   │   │   └── net_nbr_unref                                                              20   0.01%
        │   │   ├── net_context.c                                                                5556   2.90%
        │   │   │   ├── bind_default                                                              128   0.07%
        │   │   │   ├── check_used_port                                                           128   0.07%
        │   │   │   ├── context_alloc_pkt                                                          56   0.03%
        │   │   │   ├── context_finalize_packet                                                    58   0.03%
        │   │   │   ├── context_sendto                                                            600   0.31%
        │   │   │   ├── context_setup_udp_packet                                                  116   0.06%
        │   │   │   ├── context_write_data                                                         68   0.04%
        │   │   │   ├── find_available_port                                                        52   0.03%
        │   │   │   ├── find_context                                                               52   0.03%
        │   │   │   ├── get_context_dscp_ecn                                                       18   0.01%
        │   │   │   ├── get_context_priority                                                        6   0.00%
        │   │   │   ├── get_context_proxy                                                           6   0.00%
        │   │   │   ├── get_context_rcvbuf                                                          6   0.00%
        │   │   │   ├── get_context_rcvtimeo                                                       24   0.01%
        │   │   │   ├── get_context_sndbuf                                                          6   0.00%
        │   │   │   ├── get_context_sndtimeo                                                       24   0.01%
        │   │   │   ├── get_context_txtime                                                          6   0.00%
        │   │   │   ├── log_const_net_ctx                                                           8   0.00%
        │   │   │   ├── net_context_accept                                                        164   0.09%
        │   │   │   ├── net_context_bind                                                          560   0.29%
        │   │   │   ├── net_context_check                                                          92   0.05%
        │   │   │   ├── net_context_connect                                                       660   0.34%
        │   │   │   ├── net_context_create_ipv4_new                                               164   0.09%
        │   │   │   ├── net_context_create_ipv6_new                                               156   0.08%
        │   │   │   ├── net_context_get                                                           400   0.21%
        │   │   │   ├── net_context_get_option                                                    256   0.13%
        │   │   │   ├── net_context_init                                                           20   0.01%
        │   │   │   ├── net_context_listen                                                        136   0.07%
        │   │   │   ├── net_context_packet_received                                               200   0.10%
        │   │   │   ├── net_context_put                                                           132   0.07%
        │   │   │   ├── net_context_recv                                                          208   0.11%
        │   │   │   ├── net_context_ref                                                            28   0.01%
        │   │   │   ├── net_context_send                                                          138   0.07%
        │   │   │   ├── net_context_sendmsg                                                        74   0.04%
        │   │   │   ├── net_context_sendto                                                         84   0.04%
        │   │   │   ├── net_context_set_option                                                    256   0.13%
        │   │   │   ├── net_context_unref                                                          98   0.05%
        │   │   │   ├── net_context_update_recv_wnd                                                44   0.02%
        │   │   │   ├── recv_udp                                                                  220   0.11%
        │   │   │   ├── set_context_dscp_ecn                                                       30   0.02%
        │   │   │   ├── set_context_priority                                                        6   0.00%
        │   │   │   ├── set_context_proxy                                                           6   0.00%
        │   │   │   ├── set_context_rcvbuf                                                          6   0.00%
        │   │   │   ├── set_context_rcvtimeo                                                       22   0.01%
        │   │   │   ├── set_context_sndbuf                                                          6   0.00%
        │   │   │   ├── set_context_sndtimeo                                                       22   0.01%
        │   │   │   └── set_context_txtime                                                          6   0.00%
        │   │   ├── net_core.c                                                                    632   0.33%
        │   │   │   ├── __init_net_init                                                             8   0.00%
        │   │   │   ├── check_ip_addr                                                             258   0.13%
        │   │   │   ├── init_rx_queues                                                             16   0.01%
        │   │   │   ├── l3_init                                                                    32   0.02%
        │   │   │   ├── log_const_net_core                                                          8   0.00%
        │   │   │   ├── net_init                                                                   28   0.01%
        │   │   │   ├── net_process_rx_packet                                                      12   0.01%
        │   │   │   ├── net_rx                                                                     22   0.01%
        │   │   │   ├── net_send_data                                                              88   0.05%
        │   │   │   ├── process_data                                                              110   0.06%
        │   │   │   ├── processing_data                                                            30   0.02%
        │   │   │   └── services_init                                                              20   0.01%
        │   │   ├── net_if.c                                                                    10766   5.61%
        │   │   │   ├── address_expired                                                            36   0.02%
        │   │   │   ├── address_lifetime_timeout                                                  168   0.09%
        │   │   │   ├── address_start_timer                                                        72   0.04%
        │   │   │   ├── dad_timeout                                                               236   0.12%
        │   │   │   ├── get_diff_ipv4                                                              10   0.01%
        │   │   │   ├── get_diff_ipv6                                                              10   0.01%
        │   │   │   ├── get_ipaddr_diff                                                            70   0.04%
        │   │   │   ├── if_ipv4_get_addr                                                          144   0.08%
        │   │   │   ├── iface_ipv4_init                                                            28   0.01%
        │   │   │   ├── iface_ipv6_dad_init                                                        32   0.02%
        │   │   │   ├── iface_ipv6_init                                                            84   0.04%
        │   │   │   ├── iface_ipv6_nd_init                                                         32   0.02%
        │   │   │   ├── iface_ipv6_start                                                           36   0.02%
        │   │   │   ├── iface_router_add                                                          368   0.19%
        │   │   │   ├── iface_router_expired                                                      152   0.08%
        │   │   │   ├── iface_router_find_default                                                 124   0.06%
        │   │   │   ├── iface_router_init                                                          32   0.02%
        │   │   │   ├── iface_router_lookup                                                       156   0.08%
        │   │   │   ├── iface_router_notify_deletion                                               56   0.03%
        │   │   │   ├── iface_router_rm                                                            96   0.05%
        │   │   │   ├── iface_router_update_timer                                                 176   0.09%
        │   │   │   ├── init_iface                                                                 46   0.02%
        │   │   │   ├── ipv4_addr_find                                                             62   0.03%
        │   │   │   ├── ipv4_is_broadcast_address                                                  36   0.02%
        │   │   │   ├── ipv4_maddr_find                                                           110   0.06%
        │   │   │   ├── ipv6_addr_find                                                             70   0.04%
        │   │   │   ├── ipv6_prefix_find                                                           94   0.05%
        │   │   │   ├── is_proper_ipv4_address                                                     52   0.03%
        │   │   │   ├── join_mcast_allnodes                                                        24   0.01%
        │   │   │   ├── join_mcast_nodes                                                           42   0.02%
        │   │   │   ├── join_mcast_solicit_node                                                    26   0.01%
        │   │   │   ├── l2_flags_get                                                               36   0.02%
        │   │   │   ├── lock                                                                       20   0.01%
        │   │   │   ├── log_const_net_if                                                            8   0.00%
        │   │   │   ├── need_calc_checksum                                                          4   0.00%
        │   │   │   ├── net_context_send_cb                                                        16   0.01%
        │   │   │   ├── net_if_addr_init                                                          106   0.06%
        │   │   │   ├── net_if_call_link_cb                                                       100   0.05%
        │   │   │   ├── net_if_config_ipv4_get                                                    116   0.06%
        │   │   │   ├── net_if_config_ipv6_get                                                    124   0.06%
        │   │   │   ├── net_if_foreach                                                             88   0.05%
        │   │   │   ├── net_if_get_by_iface                                                        52   0.03%
        │   │   │   ├── net_if_get_default                                                         36   0.02%
        │   │   │   ├── net_if_init                                                               136   0.07%
        │   │   │   ├── net_if_ipv4_addr_add                                                      216   0.11%
        │   │   │   ├── net_if_ipv4_addr_lookup                                                   180   0.09%
        │   │   │   ├── net_if_ipv4_addr_mask_cmp                                                 112   0.06%
        │   │   │   ├── net_if_ipv4_addr_rm                                                       132   0.07%
        │   │   │   ├── net_if_ipv4_get_best_match                                                 78   0.04%
        │   │   │   ├── net_if_ipv4_get_global_addr                                                10   0.01%
        │   │   │   ├── net_if_ipv4_get_ll                                                         10   0.01%
        │   │   │   ├── net_if_ipv4_get_ttl                                                        44   0.02%
        │   │   │   ├── net_if_ipv4_is_addr_bcast                                                 136   0.07%
        │   │   │   ├── net_if_ipv4_maddr_lookup                                                  144   0.08%
        │   │   │   ├── net_if_ipv4_select_src_addr                                               280   0.15%
        │   │   │   ├── net_if_ipv4_select_src_iface                                              124   0.06%
        │   │   │   ├── net_if_ipv4_set_gw                                                         52   0.03%
        │   │   │   ├── net_if_ipv4_set_netmask                                                    52   0.03%
        │   │   │   ├── net_if_ipv6_addr_add                                                      236   0.12%
        │   │   │   ├── net_if_ipv6_addr_lookup                                                   196   0.10%
        │   │   │   ├── net_if_ipv6_addr_lookup_by_iface                                          112   0.06%
        │   │   │   ├── net_if_ipv6_addr_onlink                                                   200   0.10%
        │   │   │   ├── net_if_ipv6_addr_rm                                                       284   0.15%
        │   │   │   ├── net_if_ipv6_addr_update_lifetime                                           48   0.03%
        │   │   │   ├── net_if_ipv6_calc_reachable_time                                            60   0.03%
        │   │   │   ├── net_if_ipv6_dad_failed                                                     88   0.05%
        │   │   │   ├── net_if_ipv6_get_best_match                                                156   0.08%
        │   │   │   ├── net_if_ipv6_get_hop_limit                                                  44   0.02%
        │   │   │   ├── net_if_ipv6_get_ll                                                        128   0.07%
        │   │   │   ├── net_if_ipv6_maddr_add                                                     204   0.11%
        │   │   │   ├── net_if_ipv6_maddr_join                                                     92   0.05%
        │   │   │   ├── net_if_ipv6_maddr_lookup                                                  216   0.11%
        │   │   │   ├── net_if_ipv6_maddr_rm                                                      144   0.08%
        │   │   │   ├── net_if_ipv6_prefix_add                                                    184   0.10%
        │   │   │   ├── net_if_ipv6_prefix_init                                                   100   0.05%
        │   │   │   ├── net_if_ipv6_prefix_lookup                                                 104   0.05%
        │   │   │   ├── net_if_ipv6_prefix_rm                                                     196   0.10%
        │   │   │   ├── net_if_ipv6_prefix_set_timer                                               16   0.01%
        │   │   │   ├── net_if_ipv6_prefix_unset_timer                                             20   0.01%
        │   │   │   ├── net_if_ipv6_router_add                                                     22   0.01%
        │   │   │   ├── net_if_ipv6_router_find_default                                            12   0.01%
        │   │   │   ├── net_if_ipv6_router_lookup                                                  12   0.01%
        │   │   │   ├── net_if_ipv6_router_rm                                                       8   0.00%
        │   │   │   ├── net_if_ipv6_router_update_lifetime                                         20   0.01%
        │   │   │   ├── net_if_ipv6_select_src_addr                                               292   0.15%
        │   │   │   ├── net_if_ipv6_select_src_iface                                               80   0.04%
        │   │   │   ├── net_if_ipv6_start_dad                                                     108   0.06%
        │   │   │   ├── net_if_lookup_by_dev                                                       92   0.05%
        │   │   │   ├── net_if_mcast_monitor                                                      108   0.06%
        │   │   │   ├── net_if_need_calc_rx_checksum                                               10   0.01%
        │   │   │   ├── net_if_need_calc_tx_checksum                                               10   0.01%
        │   │   │   ├── net_if_post_init                                                          104   0.05%
        │   │   │   ├── net_if_queue_tx                                                            22   0.01%
        │   │   │   ├── net_if_recv_data                                                           20   0.01%
        │   │   │   ├── net_if_send_data                                                          180   0.09%
        │   │   │   ├── net_if_start_dad                                                          160   0.08%
        │   │   │   ├── net_if_start_rs                                                           116   0.06%
        │   │   │   ├── net_if_stop_rs                                                             48   0.03%
        │   │   │   ├── net_if_tx                                                                 176   0.09%
        │   │   │   ├── net_if_up                                                                 124   0.06%
        │   │   │   ├── net_ipv6_set_hop_limit                                                     40   0.02%
        │   │   │   ├── notify_iface_down                                                          36   0.02%
        │   │   │   ├── notify_iface_up                                                           104   0.05%
        │   │   │   ├── prefix_lifetime_expired                                                    68   0.04%
        │   │   │   ├── prefix_lifetime_timeout                                                   168   0.09%
        │   │   │   ├── prefix_start_timer                                                         96   0.05%
        │   │   │   ├── prefix_timer_remove                                                        56   0.03%
        │   │   │   ├── remove_prefix_addresses                                                    98   0.05%
        │   │   │   ├── rs_timeout                                                                324   0.17%
        │   │   │   ├── update_operational_state                                                   92   0.05%
        │   │   │   └── z_impl_net_if_get_by_index                                                 40   0.02%
        │   │   ├── net_mgmt.c                                                                    764   0.40%
        │   │   │   ├── event_msgq                                                                 52   0.03%
        │   │   │   ├── log_const_net_mgmt                                                          8   0.00%
        │   │   │   ├── mgmt_is_event_handled                                                      60   0.03%
        │   │   │   ├── mgmt_pop_event                                                             32   0.02%
        │   │   │   ├── mgmt_push_event                                                            68   0.04%
        │   │   │   ├── mgmt_rebuild_global_event_mask                                             72   0.04%
        │   │   │   ├── mgmt_run_callbacks                                                        164   0.09%
        │   │   │   ├── mgmt_thread                                                                48   0.03%
        │   │   │   ├── net_mgmt_add_event_callback                                                68   0.04%
        │   │   │   ├── net_mgmt_callback_lock                                                     20   0.01%
        │   │   │   ├── net_mgmt_del_event_callback                                                48   0.03%
        │   │   │   ├── net_mgmt_event_init                                                        72   0.04%
        │   │   │   ├── net_mgmt_event_lock                                                        20   0.01%
        │   │   │   └── net_mgmt_event_notify_with_info                                            32   0.02%
        │   │   ├── net_pkt.c                                                                    3368   1.76%
        │   │   │   ├── clone_pkt_attributes                                                      244   0.13%
        │   │   │   ├── clone_pkt_lladdr                                                           40   0.02%
        │   │   │   ├── log_const_net_pkt                                                           8   0.00%
        │   │   │   ├── net_buf_fixed_alloc_rx_bufs                                                 8   0.00%
        │   │   │   ├── net_buf_fixed_alloc_tx_bufs                                                 8   0.00%
        │   │   │   ├── net_buf_fixed_rx_bufs                                                       8   0.00%
        │   │   │   ├── net_buf_fixed_tx_bufs                                                       8   0.00%
        │   │   │   ├── net_pkt_alloc                                                              20   0.01%
        │   │   │   ├── net_pkt_alloc_buffer                                                      208   0.11%
        │   │   │   ├── net_pkt_alloc_with_buffer                                                  40   0.02%
        │   │   │   ├── net_pkt_append_buffer                                                      32   0.02%
        │   │   │   ├── net_pkt_available_buffer                                                   34   0.02%
        │   │   │   ├── net_pkt_available_payload_buffer                                           58   0.03%
        │   │   │   ├── net_pkt_clone                                                              10   0.01%
        │   │   │   ├── net_pkt_clone_internal                                                    242   0.13%
        │   │   │   ├── net_pkt_copy                                                              158   0.08%
        │   │   │   ├── net_pkt_cursor_init                                                        18   0.01%
        │   │   │   ├── net_pkt_cursor_operate                                                    218   0.11%
        │   │   │   ├── net_pkt_find_offset                                                        72   0.04%
        │   │   │   ├── net_pkt_frag_unref                                                         12   0.01%
        │   │   │   ├── net_pkt_get_contiguous_len                                                 60   0.03%
        │   │   │   ├── net_pkt_get_current_offset                                                 48   0.03%
        │   │   │   ├── net_pkt_get_data                                                           72   0.04%
        │   │   │   ├── net_pkt_get_frag                                                           32   0.02%
        │   │   │   ├── net_pkt_get_reserve_data                                                   40   0.02%
        │   │   │   ├── net_pkt_get_reserve_rx_data                                                16   0.01%
        │   │   │   ├── net_pkt_get_reserve_tx_data                                                16   0.01%
        │   │   │   ├── net_pkt_init                                                                2   0.00%
        │   │   │   ├── net_pkt_is_contiguous                                                      18   0.01%
        │   │   │   ├── net_pkt_memset                                                             24   0.01%
        │   │   │   ├── net_pkt_pull                                                              104   0.05%
        │   │   │   ├── net_pkt_read                                                               20   0.01%
        │   │   │   ├── net_pkt_read_be32                                                          50   0.03%
        │   │   │   ├── net_pkt_ref                                                                66   0.03%
        │   │   │   ├── net_pkt_remaining_data                                                     46   0.02%
        │   │   │   ├── net_pkt_remove_tail                                                        70   0.04%
        │   │   │   ├── net_pkt_rx_alloc                                                           20   0.01%
        │   │   │   ├── net_pkt_set_data                                                           12   0.01%
        │   │   │   ├── net_pkt_skip                                                               24   0.01%
        │   │   │   ├── net_pkt_trim_buffer                                                        56   0.03%
        │   │   │   ├── net_pkt_unref                                                              86   0.04%
        │   │   │   ├── net_pkt_update_length                                                      34   0.02%
        │   │   │   ├── net_pkt_write                                                              54   0.03%
        │   │   │   ├── pkt_alloc                                                                 112   0.06%
        │   │   │   ├── pkt_alloc_buffer                                                          150   0.08%
        │   │   │   ├── pkt_alloc_on_iface                                                         36   0.02%
        │   │   │   ├── pkt_alloc_with_buffer                                                     142   0.07%
        │   │   │   ├── pkt_buffer_length                                                          72   0.04%
        │   │   │   ├── pkt_cursor_advance                                                         46   0.02%
        │   │   │   ├── pkt_cursor_jump                                                            56   0.03%
        │   │   │   ├── pkt_cursor_update                                                          90   0.05%
        │   │   │   ├── pkt_estimate_headers_length                                                52   0.03%
        │   │   │   ├── pkt_get_max_len                                                            28   0.01%
        │   │   │   ├── rx_bufs                                                                    52   0.03%
        │   │   │   ├── rx_pkts                                                                    32   0.02%
        │   │   │   ├── tx_bufs                                                                    52   0.03%
        │   │   │   └── tx_pkts                                                                    32   0.02%
        │   │   ├── net_tc.c                                                                      244   0.13%
        │   │   │   ├── log_const_net_tc                                                            8   0.00%
        │   │   │   ├── net_tc_rx_init                                                            148   0.08%
        │   │   │   ├── net_tc_tx_init                                                              2   0.00%
        │   │   │   ├── net_tx_priority2tc                                                          4   0.00%
        │   │   │   ├── rx_tc2thread                                                               52   0.03%
        │   │   │   └── tc_rx_handler                                                              30   0.02%
        │   │   ├── net_timeout.c                                                                 240   0.13%
        │   │   │   ├── net_timeout_evaluate                                                       90   0.05%
        │   │   │   ├── net_timeout_remaining                                                      62   0.03%
        │   │   │   └── net_timeout_set                                                            88   0.05%
        │   │   ├── route.c                                                                      3252   1.70%
        │   │   │   ├── get_nexthop_nbr                                                            68   0.04%
        │   │   │   ├── get_nexthop_route                                                          48   0.03%
        │   │   │   ├── lock                                                                       20   0.01%
        │   │   │   ├── log_const_net_route                                                         8   0.00%
        │   │   │   ├── nbr_new                                                                    68   0.04%
        │   │   │   ├── nbr_nexthop_get                                                            18   0.01%
        │   │   │   ├── nbr_nexthop_put                                                            56   0.03%
        │   │   │   ├── net_nbr_routes                                                             12   0.01%
        │   │   │   ├── net_route_add                                                             592   0.31%
        │   │   │   ├── net_route_del                                                             184   0.10%
        │   │   │   ├── net_route_del_by_nexthop                                                  208   0.11%
        │   │   │   ├── net_route_entries_pool                                                    576   0.30%
        │   │   │   ├── net_route_entries_table_clear                                               2   0.00%
        │   │   │   ├── net_route_entry_remove                                                      2   0.00%
        │   │   │   ├── net_route_get_info                                                        108   0.06%
        │   │   │   ├── net_route_get_nbr                                                         128   0.07%
        │   │   │   ├── net_route_get_nexthop                                                     116   0.06%
        │   │   │   ├── net_route_init                                                             20   0.01%
        │   │   │   ├── net_route_lookup                                                          152   0.08%
        │   │   │   ├── net_route_nexthop_pool                                                    224   0.12%
        │   │   │   ├── net_route_nexthop_remove                                                    2   0.00%
        │   │   │   ├── net_route_packet                                                          192   0.10%
        │   │   │   ├── net_route_packet_if                                                        62   0.03%
        │   │   │   ├── net_route_update_lifetime                                                 148   0.08%
        │   │   │   ├── release_nexthop_route                                                      10   0.01%
        │   │   │   ├── route_expired                                                              28   0.01%
        │   │   │   ├── route_lifetime_timeout                                                    164   0.09%
        │   │   │   └── update_route_access                                                        36   0.02%
        │   │   ├── tcp.c                                                                       11932   6.22%
        │   │   │   ├── check_seq_list                                                             44   0.02%
        │   │   │   ├── get_tcp_nodelay                                                            22   0.01%
        │   │   │   ├── ip_header_add                                                              54   0.03%
        │   │   │   ├── is_destination_local                                                       88   0.05%
        │   │   │   ├── log_const_net_tcp                                                           8   0.00%
        │   │   │   ├── net_tcp_accept                                                            232   0.12%
        │   │   │   ├── net_tcp_conn_sem_get                                                        6   0.00%
        │   │   │   ├── net_tcp_connect                                                           480   0.25%
        │   │   │   ├── net_tcp_finalize                                                           68   0.04%
        │   │   │   ├── net_tcp_get                                                                52   0.03%
        │   │   │   ├── net_tcp_get_option                                                        152   0.08%
        │   │   │   ├── net_tcp_get_supported_mss                                                 102   0.05%
        │   │   │   ├── net_tcp_init                                                               96   0.05%
        │   │   │   ├── net_tcp_input                                                              58   0.03%
        │   │   │   ├── net_tcp_listen                                                             12   0.01%
        │   │   │   ├── net_tcp_put                                                               236   0.12%
        │   │   │   ├── net_tcp_queue_data                                                        304   0.16%
        │   │   │   ├── net_tcp_recv                                                               12   0.01%
        │   │   │   ├── net_tcp_send_data                                                          18   0.01%
        │   │   │   ├── net_tcp_set_mss_opt                                                        82   0.04%
        │   │   │   ├── net_tcp_set_option                                                        152   0.08%
        │   │   │   ├── net_tcp_tx_sem_get                                                          6   0.00%
        │   │   │   ├── net_tcp_update_recv_wnd                                                    52   0.03%
        │   │   │   ├── seq_scale                                                                  32   0.02%
        │   │   │   ├── set_tcp_nodelay                                                            44   0.02%
        │   │   │   ├── tcp_check_pending_data                                                    200   0.10%
        │   │   │   ├── tcp_cleanup_recv_queue                                                     48   0.03%
        │   │   │   ├── tcp_conn_alloc                                                            364   0.19%
        │   │   │   ├── tcp_conn_close                                                             62   0.03%
        │   │   │   ├── tcp_conn_cmp                                                               44   0.02%
        │   │   │   ├── tcp_conn_new                                                              360   0.19%
        │   │   │   ├── tcp_conn_ref                                                               28   0.01%
        │   │   │   ├── tcp_conn_search                                                            80   0.04%
        │   │   │   ├── tcp_conn_unref                                                            324   0.17%
        │   │   │   ├── tcp_conns_slab                                                             32   0.02%
        │   │   │   ├── tcp_data_get                                                              120   0.06%
        │   │   │   ├── tcp_data_len                                                               62   0.03%
        │   │   │   ├── tcp_data_received                                                          84   0.04%
        │   │   │   ├── tcp_derive_rto                                                             40   0.02%
        │   │   │   ├── tcp_endpoint_cmp                                                           46   0.02%
        │   │   │   ├── tcp_endpoint_len                                                           12   0.01%
        │   │   │   ├── tcp_endpoint_set                                                          162   0.08%
        │   │   │   ├── tcp_establish_timeout                                                      12   0.01%
        │   │   │   ├── tcp_fin_timeout                                                            34   0.02%
        │   │   │   ├── tcp_finalize_pkt                                                           48   0.03%
        │   │   │   ├── tcp_get_seq                                                                 4   0.00%
        │   │   │   ├── tcp_header_add                                                            190   0.10%
        │   │   │   ├── tcp_in                                                                   3112   1.62%
        │   │   │   ├── tcp_init_isn                                                               46   0.02%
        │   │   │   ├── tcp_lock                                                                   20   0.01%
        │   │   │   ├── tcp_options_check                                                         166   0.09%
        │   │   │   ├── tcp_options_get                                                            90   0.05%
        │   │   │   ├── tcp_out                                                                    14   0.01%
        │   │   │   ├── tcp_out_ext                                                               276   0.14%
        │   │   │   ├── tcp_out_of_order_data                                                      58   0.03%
        │   │   │   ├── tcp_pkt_linearize                                                         178   0.09%
        │   │   │   ├── tcp_pkt_peek                                                               56   0.03%
        │   │   │   ├── tcp_pkt_pull                                                               70   0.04%
        │   │   │   ├── tcp_queue_recv_data                                                       292   0.15%
        │   │   │   ├── tcp_recv                                                                  138   0.07%
        │   │   │   ├── tcp_resend_data                                                           304   0.16%
        │   │   │   ├── tcp_send                                                                   60   0.03%
        │   │   │   ├── tcp_send_ack                                                               40   0.02%
        │   │   │   ├── tcp_send_data                                                             468   0.24%
        │   │   │   ├── tcp_send_process                                                           54   0.03%
        │   │   │   ├── tcp_send_process_no_lock                                                  324   0.17%
        │   │   │   ├── tcp_send_queue_flush                                                       68   0.04%
        │   │   │   ├── tcp_send_queued_data                                                      200   0.10%
        │   │   │   ├── tcp_send_timer_cancel                                                     144   0.08%
        │   │   │   ├── tcp_send_zwp                                                              168   0.09%
        │   │   │   ├── tcp_set_seq                                                                 4   0.00%
        │   │   │   ├── tcp_short_window                                                          150   0.08%
        │   │   │   ├── tcp_state_to_str                                                          168   0.09%
        │   │   │   ├── tcp_timewait_timeout                                                       16   0.01%
        │   │   │   ├── tcp_unsent_len                                                             42   0.02%
        │   │   │   ├── tcp_update_recv_wnd                                                        78   0.04%
        │   │   │   ├── tcp_validate_seq                                                           58   0.03%
        │   │   │   ├── tcp_window_full                                                            18   0.01%
        │   │   │   ├── tcpv4_init_isn                                                             96   0.05%
        │   │   │   ├── tcpv6_init_isn                                                            112   0.06%
        │   │   │   └── th_get                                                                     76   0.04%
        │   │   ├── udp.c                                                                         326   0.17%
        │   │   │   ├── log_const_net_udp                                                           8   0.00%
        │   │   │   ├── net_udp_create                                                             58   0.03%
        │   │   │   ├── net_udp_finalize                                                          112   0.06%
        │   │   │   ├── net_udp_input                                                             104   0.05%
        │   │   │   └── net_udp_register                                                           44   0.02%
        │   │   └── utils.c                                                                      2500   1.30%
        │   │       ├── calc_chksum                                                               276   0.14%
        │   │       ├── convert_port                                                               66   0.03%
        │   │       ├── log_const_net_utils                                                         8   0.00%
        │   │       ├── net_byte_to_hex                                                            58   0.03%
        │   │       ├── net_calc_chksum                                                           236   0.12%
        │   │       ├── net_calc_chksum_ipv4                                                       48   0.03%
        │   │       ├── net_ipaddr_parse                                                          110   0.06%
        │   │       ├── net_ipv4_broadcast_address                                                  8   0.00%
        │   │       ├── net_ipv4_unspecified_address                                                8   0.00%
        │   │       ├── net_ipv6_unspecified_address                                                8   0.00%
        │   │       ├── net_sprint_ll_addr_buf                                                     96   0.05%
        │   │       ├── net_value_to_udec                                                          84   0.04%
        │   │       ├── offset_based_swap8                                                         14   0.01%
        │   │       ├── parse_ipv4                                                                212   0.11%
        │   │       ├── parse_ipv6                                                                262   0.14%
        │   │       ├── pkt_calc_chksum                                                            86   0.04%
        │   │       ├── z_impl_net_addr_ntop                                                      440   0.23%
        │   │       └── z_impl_net_addr_pton                                                      480   0.25%
        │   └── lib                                                                              8378   4.37%
        │       ├── config                                                                        728   0.38%
        │       │   └── init.c                                                                    728   0.38%
        │       │       ├── __init_init_app                                                         8   0.00%
        │       │       ├── check_interface                                                        64   0.03%
        │       │       ├── counter                                                                24   0.01%
        │       │       ├── iface_find_cb                                                          32   0.02%
        │       │       ├── iface_up_handler                                                       36   0.02%
        │       │       ├── init_app                                                               20   0.01%
        │       │       ├── ipv4_addr_add_handler                                                  64   0.03%
        │       │       ├── log_const_net_config                                                    8   0.00%
        │       │       ├── net_config_init_app                                                    56   0.03%
        │       │       ├── net_config_init_by_iface                                              308   0.16%
        │       │       ├── services_notify_ready                                                  44   0.02%
        │       │       ├── setup_dhcpv4                                                           40   0.02%
        │       │       └── waiter                                                                 24   0.01%
        │       ├── dns                                                                          1368   0.71%
        │       │   └── resolve.c                                                                1368   0.71%
        │       │       ├── dns_init_resolver                                                      16   0.01%
        │       │       ├── dns_msg_pool                                                           52   0.03%
        │       │       ├── dns_postprocess_server                                                120   0.06%
        │       │       ├── dns_qname_pool                                                         52   0.03%
        │       │       ├── dns_resolve_cancel_all                                                 46   0.02%
        │       │       ├── dns_resolve_cancel_slot                                                32   0.02%
        │       │       ├── dns_resolve_close_locked                                              108   0.06%
        │       │       ├── dns_resolve_get_default                                                 8   0.00%
        │       │       ├── dns_resolve_init                                                       50   0.03%
        │       │       ├── dns_resolve_init_locked                                               384   0.20%
        │       │       ├── dns_resolve_reconfigure                                               108   0.06%
        │       │       ├── dns_server_exists                                                      84   0.04%
        │       │       ├── dns_servers_exists                                                    104   0.05%
        │       │       ├── invoke_query_callback                                                  18   0.01%
        │       │       ├── log_const_net_dns_resolve                                               8   0.00%
        │       │       ├── net_buf_fixed_alloc_dns_msg_pool                                        8   0.00%
        │       │       ├── net_buf_fixed_alloc_dns_qname_pool                                      8   0.00%
        │       │       ├── net_buf_fixed_dns_msg_pool                                              8   0.00%
        │       │       ├── net_buf_fixed_dns_qname_pool                                            8   0.00%
        │       │       ├── release_query                                                          22   0.01%
        │       │       ├── server_is_llmnr                                                        62   0.03%
        │       │       └── server_is_mdns                                                         62   0.03%
        │       └── sockets                                                                      6282   3.28%
        │           ├── getaddrinfo.c                                                               8   0.00%
        │           │   └── log_const_net_sock_addr                                                 8   0.00%
        │           └── sockets.c                                                                6274   3.27%
        │               ├── __net_socket_register_50_af_inet46                                     16   0.01%
        │               ├── fifo_wait_non_empty                                                    50   0.03%
        │               ├── inet_is_supported                                                      14   0.01%
        │               ├── log_const_net_sock                                                      8   0.00%
        │               ├── send_check_and_wait                                                   362   0.19%
        │               ├── sock_accept_vmeth                                                       8   0.00%
        │               ├── sock_bind_vmeth                                                         8   0.00%
        │               ├── sock_close_vmeth                                                        8   0.00%
        │               ├── sock_connect_vmeth                                                      8   0.00%
        │               ├── sock_fd_op_vtable                                                      64   0.03%
        │               ├── sock_get_pkt_src_addr                                                 302   0.16%
        │               ├── sock_getpeername_vmeth                                                  8   0.00%
        │               ├── sock_getsockname_vmeth                                                  8   0.00%
        │               ├── sock_getsockopt_vmeth                                                  22   0.01%
        │               ├── sock_ioctl_vmeth                                                      190   0.10%
        │               ├── sock_listen_vmeth                                                       8   0.00%
        │               ├── sock_read_vmeth                                                        20   0.01%
        │               ├── sock_recvfrom_vmeth                                                    30   0.02%
        │               ├── sock_sendmsg_vmeth                                                      8   0.00%
        │               ├── sock_sendto_vmeth                                                      30   0.02%
        │               ├── sock_setsockopt_vmeth                                                  22   0.01%
        │               ├── sock_shutdown_vmeth                                                     8   0.00%
        │               ├── sock_write_vmeth                                                       20   0.01%
        │               ├── timeout_recalc                                                         66   0.03%
        │               ├── z_impl_zsock_close                                                     74   0.04%
        │               ├── z_impl_zsock_connect                                                   94   0.05%
        │               ├── z_impl_zsock_recvfrom                                                 112   0.06%
        │               ├── z_impl_zsock_sendto                                                   112   0.06%
        │               ├── z_impl_zsock_socket                                                   164   0.09%
        │               ├── zsock_accept_ctx                                                      300   0.16%
        │               ├── zsock_accepted_cb                                                      64   0.03%
        │               ├── zsock_bind_ctx                                                         88   0.05%
        │               ├── zsock_close_ctx                                                        80   0.04%
        │               ├── zsock_connect_ctx                                                     224   0.12%
        │               ├── zsock_connected_cb                                                     52   0.03%
        │               ├── zsock_ctx_set_lock                                                      6   0.00%
        │               ├── zsock_flush_queue                                                      56   0.03%
        │               ├── zsock_getpeername_ctx                                                 218   0.11%
        │               ├── zsock_getsockname_ctx                                                 164   0.09%
        │               ├── zsock_getsockopt_ctx                                                  198   0.10%
        │               ├── zsock_listen_ctx                                                       72   0.04%
        │               ├── zsock_poll_prepare_ctx                                                214   0.11%
        │               ├── zsock_poll_update_ctx                                                 172   0.09%
        │               ├── zsock_received_cb                                                     130   0.07%
        │               ├── zsock_recv_dgram                                                      362   0.19%
        │               ├── zsock_recv_stream                                                     454   0.24%
        │               ├── zsock_recvfrom_ctx                                                    116   0.06%
        │               ├── zsock_sendmsg_ctx                                                     160   0.08%
        │               ├── zsock_sendto_ctx                                                      260   0.14%
        │               ├── zsock_setsockopt_ctx                                                  712   0.37%
        │               ├── zsock_shutdown_ctx                                                    144   0.08%
        │               ├── zsock_socket_internal                                                 140   0.07%
        │               └── zsock_wait_data                                                        44   0.02%
        ├── pm                                                                                    868   0.45%
        │   ├── pm.c                                                                              692   0.36%
        │   │   ├── log_const_pm                                                                    8   0.00%
        │   │   ├── pm_exit_pos_ops                                                                32   0.02%
        │   │   ├── pm_state_notify                                                               200   0.10%
        │   │   ├── pm_system_resume                                                               72   0.04%
        │   │   └── pm_system_suspend                                                             380   0.20%
        │   ├── policy.c                                                                          160   0.08%
        │   │   ├── max_latency_ticks                                                               4   0.00%
        │   │   ├── pm_policy_next_state                                                          152   0.08%
        │   │   └── pm_policy_state_lock_is_active                                                  4   0.00%
        │   └── state.c                                                                            16   0.01%
        │       └── pm_state_cpu_get_all                                                           16   0.01%
        └── random                                                                                238   0.12%
            └── rand32_entropy_device.c                                                           238   0.12%
                ├── rand_get                                                                      132   0.07%
                ├── z_impl_sys_rand32_get                                                          96   0.05%
                └── z_impl_sys_rand_get                                                            10   0.01%
==============================================================================================================
                                                                                               191792
