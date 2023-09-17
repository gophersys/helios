#include "cipher.h"

// Standard includes
#include <stdio.h>

// Zephyr includes
#include <zephyr/kernel.h>

// Private includes
#include "tal.h"
#include "utils.h"

/*-----------------------------------------------------------------------------------------------------
 *                                                                                        Configuration
 *---------------------------------------------------------------------------------------------------*/
LOG_MODULE_DECLARE(protocol, LOG_LEVEL_DBG);

#ifndef CONFIG_CIPHER_RECV_BUFFER_SIZE
#define CONFIG_CIPHER_RECV_BUFFER_SIZE 1024
#endif

#ifndef CONFIG_CIPHER_RECV_BUFFERS
#define CONFIG_CIPHER_RECV_BUFFERS 10
#endif

/*-----------------------------------------------------------------------------------------------------
 *                                                                                 Private Data & Types
 *---------------------------------------------------------------------------------------------------*/

typedef struct buffer_item_t
{
    bool used;
    uint8_t data[CONFIG_CIPHER_RECV_BUFFER_SIZE];
    struct buffer_item_t *next;
} buffer_item_t;

static buffer_item_t buffer_pool[CONFIG_CIPHER_RECV_BUFFERS];
static buffer_item_t *free_list = NULL;

/*-----------------------------------------------------------------------------------------------------
 *                                                                                    Private Functions
 *---------------------------------------------------------------------------------------------------*/
static void cipher_buffer_pool_init(void)
{
    for (uint16_t i = 0; i < CONFIG_CIPHER_RECV_BUFFERS; i++)
    {
        buffer_pool[i].used = false;
        buffer_pool[i].next = &buffer_pool[i + 1];
    }

    buffer_pool[CONFIG_CIPHER_RECV_BUFFERS - 1].used = false;
    buffer_pool[CONFIG_CIPHER_RECV_BUFFERS - 1].next = NULL;

    free_list = &buffer_pool[0];
}

/*-----------------------------------------------------------------------------------------------------
 *                                                                                           Public API
 *---------------------------------------------------------------------------------------------------*/
uint8_t *cipher_new_buffer(size_t size)
{
    __ASSERT(size <= CONFIG_CIPHER_RECV_BUFFER_SIZE, "max allowed buffer size is %d", CONFIG_CIPHER_RECV_BUFFER_SIZE);

    static bool initialized = false;
    if (!initialized)
    {
        cipher_buffer_pool_init();
        initialized = true;
    }

    if (free_list == NULL)
        ERROR("No buffers available, increase size. Current size: %d", CONFIG_CIPHER_RECV_BUFFERS);

    buffer_item_t *available_item = free_list;
    free_list = available_item->next;
    available_item->used = true;

    return available_item->data;
}

void cipher_free_buffer(uint8_t *buffer)
{
    for (int i = 0; i < CONFIG_CIPHER_RECV_BUFFERS; i++)
    {
        if (buffer_pool[i].data == buffer)
        {
            buffer_pool[i].used = false;
            buffer_pool[i].next = free_list;
            free_list = &buffer_pool[i];
            return;
        }
    }
}
