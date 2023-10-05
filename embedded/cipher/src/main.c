// Zephyr includes
#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>
LOG_MODULE_REGISTER(app);

// Cipher includes
#include "cipher/test/include/cipher_tests.h"
#include "daemon/api.h"
#include "daemon/fifo.h"
#include "daemon/registry.h"
#include "utils/err.h"

// App includes
#include "autogen/autogen.h"

int main(void) {
    LOG_RAW("\n\n%s\n", "********** Cipher Protocol App **********");
    cipher_test_rpc();
}
