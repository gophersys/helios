#ifndef ALT_DRV_TEST_SRVC_H
#define ALT_DRV_TEST_SRVC_H

#include <stdbool.h>
#include <stdint.h>

// Cipher includes
#include "daemon/daemon.h"

/*-----------------------------------------------------------------------------------------------------
 *                                                                                        Message Types
 *---------------------------------------------------------------------------------------------------*/

typedef struct __attribute__((packed)) {
} test_request_t;

typedef struct __attribute__((packed)) {
     enum {
        ALT_TEST_ERR_FATAL = 0,
        ALT_TEST_ERR_FIXTURE = 0, // There was an issue communicating with the test fixture
        ALT_TEST_ERR_RESULTS = 0, // The values of the altimeter don't match those of the test bench
    } err;
    bool success;
} test_response_t;

/*-----------------------------------------------------------------------------------------------------
 *                                                                                    Local RPC Handler
 *---------------------------------------------------------------------------------------------------*/
test_response_t alt_drv_test_rpc_begin_test_handler(test_request_t request);

/*-----------------------------------------------------------------------------------------------------
 *                                                                                   Remote RPC Request
 *---------------------------------------------------------------------------------------------------*/
test_response_t alt_drv_test_rpc_begin_test(cipher_daemon_t* d, cipher_rpc_user_info_t* info,
                                                test_request_t request);

/*-----------------------------------------------------------------------------------------------------
 *                                                                                 Service Registration
 *---------------------------------------------------------------------------------------------------*/
cipher_service_entry_t* alt_drv_test_get_services(size_t* num_services);

#endif