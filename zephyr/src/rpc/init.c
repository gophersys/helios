// Zephyr includes
#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>
#include <zephyr/random/random.h>

// Cipher includes
#include "config/default.h"
#include "daemon/daemon.h"
#include "utils/err.h"

// Private includes
#include "threads.h"

void cipher_rpc_init(cipher_daemon_t* d) {

    k_fifo_init(&d->rpc.packets_event_queue);
    k_fifo_init(&d->rpc.ctrl_event_queue);
    k_fifo_init(&d->rpc.local_request_event_queue);

    k_heap_init(&d->rpc.heap, d->rpc.heap_mem, sizeof(d->rpc.heap_mem));

    d->rpc.t_id = k_thread_create(&d->rpc.t_data,
                                  d->rpc.t_stack,
                                  K_KERNEL_STACK_SIZEOF(d->rpc.t_stack),
                                  cipher_rpc_thread,
                                  (void*)d, NULL, NULL,
                                  RPC_THREAD_PRIORITY,
                                  0,
                                  K_FOREVER);

    k_thread_name_set(d->rpc.t_id, "cipher_rpc");
    k_thread_start(d->rpc.t_id);

    for (size_t i = 0; i < ARRAY_SIZE(d->rpc.workers); i++) {
        cipher_rpc_worker_thread_t* worker = &d->rpc.workers[i];

        k_fifo_init(&worker->packets_event_queue);

        worker->t_id = k_thread_create(&worker->t_data,
                                       worker->t_stack,
                                       K_KERNEL_STACK_SIZEOF(worker->t_stack),
                                       cipher_rpc_worker_thread,
                                       (void*)d, (void*)worker, NULL,
                                       RPC_THREAD_PRIORITY,
                                       0,
                                       K_FOREVER);

        k_thread_name_set(worker->t_id, "cipher_rpc_worker");  // TODO: set id
        k_thread_start(worker->t_id);
    }
}