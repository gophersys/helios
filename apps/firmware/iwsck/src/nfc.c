/* NFC T2T tag — emits NDEF text record readable by phone */

#include <zephyr/kernel.h>
#include <zephyr/shell/shell.h>
#include <nfc_t2t_lib.h>
#include <nfc/ndef/msg.h>
#include <nfc/ndef/text_rec.h>
#include <string.h>

static uint8_t ndef_msg_buf[256];
static bool nfc_active;

static void nfc_callback(void *context, nfc_t2t_event_t event,
			 const uint8_t *data, size_t data_length)
{
	ARG_UNUSED(context);
	ARG_UNUSED(data);
	ARG_UNUSED(data_length);

	switch (event) {
	case NFC_T2T_EVENT_FIELD_ON:
		printk("[nfc] Field ON\n");
		break;
	case NFC_T2T_EVENT_FIELD_OFF:
		printk("[nfc] Field OFF\n");
		break;
	default:
		break;
	}
}

static int cmd_start(const struct shell *sh, size_t argc, char **argv)
{
	if (nfc_active) {
		shell_warn(sh, "NFC already active");
		return 0;
	}

	const char *text = "IWSCK-A1";
	if (argc >= 2) {
		text = argv[1];
	}

	int err = nfc_t2t_setup(nfc_callback, NULL);
	if (err) {
		shell_error(sh, "nfc_t2t_setup: %d", err);
		return err;
	}

	uint8_t lang_code[] = "en";
	uint32_t len = sizeof(ndef_msg_buf);

	NFC_NDEF_MSG_DEF(nfc_msg, 1);
	NFC_NDEF_TEXT_RECORD_DESC_DEF(text_rec, UTF_8, lang_code,
				      sizeof(lang_code) - 1,
				      (uint8_t *)text, strlen(text));

	err = nfc_ndef_msg_record_add(&NFC_NDEF_MSG(nfc_msg),
				      &NFC_NDEF_TEXT_RECORD_DESC(text_rec));
	if (err) {
		shell_error(sh, "record_add: %d", err);
		return err;
	}

	err = nfc_ndef_msg_encode(&NFC_NDEF_MSG(nfc_msg), ndef_msg_buf, &len);
	if (err) {
		shell_error(sh, "encode: %d", err);
		return err;
	}

	err = nfc_t2t_payload_set(ndef_msg_buf, len);
	if (err) {
		shell_error(sh, "payload_set: %d", err);
		return err;
	}

	err = nfc_t2t_emulation_start();
	if (err) {
		shell_error(sh, "emulation_start: %d", err);
		return err;
	}

	nfc_active = true;
	shell_print(sh, "NFC tag active: \"%s\"", text);
	return 0;
}

static int cmd_stop(const struct shell *sh, size_t argc, char **argv)
{
	ARG_UNUSED(argc);
	ARG_UNUSED(argv);

	if (!nfc_active) {
		shell_warn(sh, "NFC not active");
		return 0;
	}

	nfc_t2t_emulation_stop();
	nfc_t2t_done();
	nfc_active = false;
	shell_print(sh, "NFC stopped");
	return 0;
}

SHELL_STATIC_SUBCMD_SET_CREATE(sub_nfc,
	SHELL_CMD_ARG(start, NULL, "Start NFC tag [text]", cmd_start, 1, 1),
	SHELL_CMD(stop, NULL, "Stop NFC tag", cmd_stop),
	SHELL_SUBCMD_SET_END
);
SHELL_CMD_REGISTER(nfc, &sub_nfc, "NFC T2T tag", NULL);
