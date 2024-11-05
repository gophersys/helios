#ifndef THREADS_VITALS_H_
#define THREADS_VITALS_H_

// Standard includes
#include <stdbool.h>

// Thread includes
#include "types.h"

/**
 * @brief Initialize the vitals thread
 *
 * @param p_config  The configuration for the vitals thread
 * @param p_thread  The thread structure to initialize
 * @return true     If the thread was initialized successfully
 * @return false    If the thread was not initialized successfully
 */
bool vitals_thread_init(const vitals_thread_config_t *p_config, vitals_thread_t *p_thread);

#endif  // THREADS_VITALS_H_
