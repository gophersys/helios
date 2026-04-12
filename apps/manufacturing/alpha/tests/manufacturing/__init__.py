"""Alpha manufacturing tests — electrical, flash, POST.

Three sequential stages run per DUT slot:
  1. test_electrical  — power rail validation (UVLO, regulation, charger)
  2. test_fw_flash    — J-Link firmware programming + AP protect
  3. test_post        — boot, hardware verification, personalization, IPC rekey
"""
