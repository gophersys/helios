#ifndef COREKINECT_IFACE_UTILS_ASSERT_H
#define COREKINECT_IFACE_UTILS_ASSERT_H

// Standard includes
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

// Zephyr includes
#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>

/**
 * @def ASSERT_NOT_NULL(a)
 * @brief Checks if the variable is NULL.
 *
 * @param a The variable to check.
 */
#define ASSERT_NOT_NULL(a)                                           \
    if ((a) == NULL) {                                               \
        LOG_ERR("Assertion failed in %s: %s is NULL", __func__, #a); \
        return false;                                                \
    }

/**
 * @def ASSERT_NOT_FALSE(f)
 * @brief Checks if a function returns false.
 *
 * @param f The function to check.
 */
#define ASSERT_NOT_FALSE(f)                       \
    if ((f) == false) {                           \
        LOG_ERR("%s failed in %s", #f, __func__); \
        return false;                             \
    }

/**
 * @def ASSERT_INITIALIZED(i)
 * @brief Checks if the assembler is initialized.
 *
 * @param i The boolean indicating succesfull initialization.
 */
#define ASSERT_INITIALIZED(i)                                                                      \
    if ((i) == false) {                                                                            \
        LOG_ERR("%s", "Attempting to use assembler without initialization. Did you call init()?"); \
        return false;                                                                              \
    }

/**
 * @def ASSERT_MALLOC(m)
 * @brief Checks if a memory allocationw as succesful
 *
 * @param f The function to check.
 */
//TODO: This macro could also take in the heap where it failed as an arguement to print what needs to be done to what heap
#define ASSERT_MALLOC(m)                                                                \
    if ((m) == NULL) {                                                                  \
        LOG_ERR("%s allocation failed in %s:%d->%s", #m, __FILE__, __LINE__, __func__); \
        k_fatal_halt(0);                                                                   \
    }

/**
 * @def SOFTWARE_BUG(what, expected, action)
 * @brief Reports a software bug with detailed information using Zephyr's logging system and halts execution.
 *
 * @param what Description of what happened.
 * @param expected Description of what was expected to happen.
 * @param action Suggested action or remedy.
 */
// TODO: This would actually be a great macro to have defined
#define SOFTWARE_BUG(what, expected, action)                                                                         \
    do {                                                                                                             \
        LOG_ERR("Software Bug Detected in %s at %s:%d\n\rWhat Happened: %s\n\rExpected: %s\n\rSuggested Action: %s", \
                __func__, __FILE__, __LINE__, what, expected, action);                                               \
        k_fatal_halt(0);                                                                                             \
    } while (0)

#endif  // COREKINECT_IFACE_UTILS_ASSERT_H