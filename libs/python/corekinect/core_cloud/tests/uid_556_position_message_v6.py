from corekinect.core_cloud.messages import PositionMsgV6

last_pos = PositionMsgV6.get_last(dut_id=0x70B3D584C01E1445, env="VAL_1_0")
print(last_pos.temperature_fahrenheit)
breakpoint
