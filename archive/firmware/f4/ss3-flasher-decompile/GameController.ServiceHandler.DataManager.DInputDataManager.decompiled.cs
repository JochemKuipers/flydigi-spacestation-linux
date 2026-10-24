using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading;
using System.Threading.Tasks;
using GameController.ServiceHandler.Drivers;
using GameController.ServiceHandler.Service;
using GameController.ServiceHandler.Service.Protocol;
using HidSharp;
using LibCommon.Command;
using LibCommon.Common.Delegate;
using LibCommon.Config;
using LibCommon.Model;
using LibCommon.Model.ProtocolModel;
using LibCommon.Services.Data;
using LibCommon.Utils;
using Newtonsoft.Json;

namespace GameController.ServiceHandler.DataManager;

public class DInputDataManager : UsbDataManager, IUsbDataManager
{
	public static byte PackageLength = Constant.PackLength;

	public static byte LEDPackageLength = Constant.LedPackLengthNew;

	public new static DInputDataManager instance;

	public static DeviceStream deviceStream;

	public static Report eReport;

	public new static int ReportIndex;

	public static GamepadConfigReport CurrentGamepadConfig;

	public byte[] LastDinputBuffer = new byte[32];

	public bool IsOnlyReadCFGID;

	private IDelegateCallback WriteConfigCallback;

	private List<List<byte>> FullConfigList = new List<List<byte>>();

	private static int FullPackageCount = 0;

	private static int ReadPackageId = -1;

	private int CurrentWPIndex;

	public bool IsWriting;

	public bool IsReading;

	public bool IsLEDReading;

	public bool IsFlash;

	public static bool IsWriteFlash = false;

	public bool IsActiveReadCFGID;

	private FDGDeviceExtChipInfo mFDGExtChipInfo;

	private int currentIndex;

	public List<byte> TempConfigListByte = new List<byte>();

	public List<byte> TempLEDConfigListByte = new List<byte>();

	public byte[] TempConfigArrByte;

	public byte[] TempLEDConfigArrByte;

	private static bool IsSuccessNotify = false;

	public static DInputDataManager GetCurrentInstance()
	{
		if (instance == null)
		{
			instance = new DInputDataManager();
		}
		return instance;
	}

	public bool CallbackDataReceive(Report e)
	{
		try
		{
			eReport = e;
			ReportIndex = eReport.reportID;
			byte[] reportBuff = e.reportBuff;
			if (!UsbDataManager.gFdgDeviceDic.ContainsKey(ReportIndex))
			{
				FLog.d("error error!!!!:ReportIndex:" + ReportIndex);
				return false;
			}
			if (UsbDataManager.IsOpenKeyMouFunc && reportBuff[0] == 4 && reportBuff[1] == 254)
			{
				if (GamePadVersionUtils.IsFP3Serial(UsbDataManager.FDGDeviceInfo) || GamePadVersionUtils.IsFP4Serial(UsbDataManager.FDGDeviceInfo))
				{
					if (!Enumerable.SequenceEqual(LastDinputBuffer, reportBuff))
					{
						KeyMouDataParse.ParseDInputData(reportBuff, UsbDataManager.FDGDeviceInfo);
					}
				}
				else
				{
					KeyMouDataParse.ParseDInputData(reportBuff, UsbDataManager.FDGDeviceInfo);
				}
			}
			if (reportBuff[0] == 4 && reportBuff[1] == 254)
			{
				PS5Driver.SendReportData2PS5(reportBuff, UsbDataManager.FDGDeviceInfo);
			}
			if (reportBuff[0] == 4 && reportBuff[1] == byte.MaxValue && reportBuff[2] == 240)
			{
				ResolveUsbData(reportBuff);
			}
			if ((reportBuff[0] == 4 && reportBuff[1] == 240 && reportBuff[2] == byte.MaxValue) || (reportBuff[0] == 4 && reportBuff[1] == 241 && reportBuff[2] == byte.MaxValue) || (reportBuff[0] == 4 && reportBuff[1] == 35))
			{
				ResolveUsbData(reportBuff);
			}
			if (reportBuff[0] == 4 && reportBuff[1] == 17)
			{
				FLog.d("接收器返回：接收器版本 回调" + DataUtils.ByteToHexString(reportBuff));
				HandleDongleInfo(reportBuff);
			}
			if (UsbDataManager.IsListenOperationData)
			{
				byte[] buffer = DataUtils.DInputFormatOperateEventData(reportBuff);
				InvokeUsbData(buffer);
			}
			else if (UsbDataManager.IsListenMappingData && reportBuff[0] == 4 && reportBuff[1] == 254 && reportBuff[2] == 102)
			{
				byte[] buffer2 = DataUtils.DInputFormatOperateEventData(reportBuff);
				InvokeUsbMappingData(buffer2);
			}
			byte[] bytes = DataUtils.DInputFormatOperateEventData(reportBuff);
			try
			{
				KeyCountService.RecordQueue.Enqueue(CommonUtils.byteToHexString(bytes));
			}
			catch (Exception)
			{
			}
			LastDinputBuffer = reportBuff;
		}
		catch (Exception ex2)
		{
			FLog.d("OnDataReceived exception:" + ex2.Message + " stack trace:" + ex2.StackTrace);
		}
		return true;
	}

	public void ResolveUsbData(byte[] recBuf)
	{
		string cmdKey = GetCmdKey(recBuf, isAck: true, isDInput: true);
		if ((recBuf[3] & 0xFF) == 170 && (recBuf[4] & 0xFF) == 172)
		{
			FLog.d("DInput 接收器返回：配置Id：" + DataUtils.ByteToHexString(recBuf));
			return;
		}
		if ((recBuf[15] & 0xFF) == 235)
		{
			FLog.d("DInput 接收器返回：手柄配置信息回调" + DataUtils.ByteToHexString(recBuf));
			HandleGamepadConfigReadCB(recBuf);
			return;
		}
		if ((recBuf[15] & 0xFF) == 229)
		{
			FLog.d("接收器返回：LED配置信息回调" + DataUtils.ByteToHexString(recBuf));
			HandleLEDConfigReadCB(recBuf);
			return;
		}
		if (recBuf[0] == 4 && recBuf[1] == 17)
		{
			FLog.d("接收器返回：接收器版本 回调" + DataUtils.ByteToHexString(recBuf));
			HandleDongleInfo(recBuf);
		}
		if ((recBuf[15] & 0xFF) == 234)
		{
			HandleWriteGamepadConfigCBK(recBuf);
		}
		if ((recBuf[15] & 0xFF) == 231)
		{
			HandleWriteGamepadConfigCBK(recBuf);
		}
		if ((recBuf[15] & 0xFF) == 51)
		{
			HandleWriteGamepadConfigCBK(recBuf);
		}
		if ((recBuf[15] & 0xFF) == 236 && (!UsbDataManager._ackCmdFlags.TryGetValue(cmdKey, out var value) || !value))
		{
			FLog.d("接收器返回 手柄信息:" + DataUtils.ByteToHexString(recBuf));
			HandleGamePadInfo(recBuf);
			return;
		}
		if ((recBuf[0] & 0xFF) == 4 && recBuf[3] == 160 && recBuf[4] == 2)
		{
			FLog.d("接收器返回：扳机参数信息：" + DataUtils.ByteToHexString(recBuf));
			return;
		}
		if ((recBuf[3] & 0xFF) == 245 && recBuf[4] == 1)
		{
			FLog.d("接收器返回：手柄扩展信息" + DataUtils.ByteToHexString(recBuf));
			string cmdKeyV = GetCmdKeyV3(recBuf, isAck: true, isDInput: true);
			if (!UsbDataManager._ackCmdFlags.TryGetValue(cmdKeyV, out var value2) || !value2)
			{
				HanderExtensionChipInfo(recBuf);
			}
			return;
		}
		if ((recBuf[3] & 0xFF) == 242 && recBuf[4] == 3)
		{
			FLog.d("接收器返回：屏幕状态栏信息," + DataUtils.ByteToHexString(recBuf));
			HanderScreenInfo(recBuf);
			HanderScreenInfoSleepTime(recBuf);
			return;
		}
		if ((recBuf[3] & 0xFF) == 242 && recBuf[4] == 4)
		{
			FLog.d("接收器返回：屏幕休眠," + DataUtils.ByteToHexString(recBuf));
			HanderScreenInfoSleepTime(recBuf);
			return;
		}
		if (recBuf[0] == 4 && recBuf[1] == 240)
		{
			FLog.d("onCallbackHandle start cmd:" + DataUtils.ByteToHexString(recBuf));
			ScreenDataTransService.HandlerPicData(24, 0, 0, 0);
		}
		if (recBuf[0] == 4 && recBuf[1] == 35)
		{
			ScreenDataTransService.HandlerPicData(24, 0, 0, 0);
			return;
		}
		if (recBuf[3] == 90 && recBuf[4] == 165)
		{
			byte b = recBuf[5];
			if ((uint)(b - 208) <= 3u)
			{
				ScreenDataTransService.HandlerPicData(84, recBuf[7], 0, 0);
				return;
			}
		}
		if ((recBuf[3] & 0xFF) == 250 && recBuf[4] == 160)
		{
			HandlerUUIDCB(recBuf);
		}
		if ((recBuf[3] & 0xFF) == 80 && recBuf[4] == 3)
		{
			HandlerSaveFlashConfigCB(recBuf);
		}
		if ((recBuf[3] & 0xFF) == 80 && recBuf[4] == 2)
		{
			HandlerReadRandomIdCB(recBuf);
		}
		if ((recBuf[3] & 0xFF) == 80 && recBuf[4] == 5)
		{
			HandlerSwitchConfigIdCB(recBuf);
		}
		if ((recBuf[3] & 0xFF) == 80 && recBuf[4] == 6)
		{
			HandlerAllFuncSetConfigCB(recBuf);
		}
	}

	public void GetDeviceInfo()
	{
		byte[] GamepadInfoCmd = DongleCommand.getDeviceInfoInAndroid();
		FLog.d("【DInput: GetDeviceInfo】：");
		SendByteArray(GamepadInfoCmd);
		string cmdKey = GetCmdKey(GamepadInfoCmd);
		UsbDataManager._ackCmdFlags[cmdKey] = false;
		UsbDataManager.cts = new CancellationTokenSource();
		Task.Delay(UsbDataManager.RetrayGamePadInfoDelayCheckTime, UsbDataManager.cts.Token).ContinueWith((Task t) =>
		{
			if (!t.IsCanceled)
			{
				FLog.d($"【Gamepad Info Retry：{UsbDataManager.retries}】");
				ResendDataPacket(GamepadInfoCmd);
			}
		});
	}

	public void GetDongleInfo()
	{
		byte[] dongleVersionCommand = DongleCommand.getDongleVersionCommand();
		FLog.d("【DInput: GetDongleInfo】：");
		SendByteArray(dongleVersionCommand);
		string cmdKey = GetCmdKey(dongleVersionCommand);
		UsbDataManager._ackCmdFlags[cmdKey] = false;
		UsbDataManager.dongle_cts = new CancellationTokenSource();
		Task.Delay(500 + 100 * UsbDataManager.MaxRetryGamepadInfoNum, UsbDataManager.dongle_cts.Token).ContinueWith((Task t) =>
		{
			FLog.d($"【GetDongleInfo Retry 1：{UsbDataManager.retries}_{UsbDataManager.MaxRetryGamepadInfoNum}_{t.IsCanceled}】");
			if (!t.IsCanceled && UsbDataManager.retries < UsbDataManager.MaxRetryGamepadInfoNum)
			{
				FLog.d($"【GetDongleInfo Retry 2：{UsbDataManager.retries}】");
				UsbDataManager.retries++;
				GetDongleInfo();
			}
		});
	}

	private void ResendDataPacket(byte[] Cmd)
	{
		if (UsbDataManager.retries < UsbDataManager.MaxRetryNum && currentIndex == CurrentWPIndex)
		{
			UsbDataManager.retries++;
			GetDeviceInfo();
		}
	}

	public bool SwitchAndroid2XInput()
	{
		byte[] switchAndroid2XInput = DongleCommand.getSwitchAndroid2XInput();
		string text = DataUtils.BytesToHexString(switchAndroid2XInput);
		FLog.d("【Switch Mode】DInput=>XInput CMD:" + text);
		SendByteArray(switchAndroid2XInput);
		return true;
	}

	public bool SwitchAndroid2OTA()
	{
		byte[] switchAndroid2OTA = DongleCommand.getSwitchAndroid2OTA();
		string text = DataUtils.BytesToHexString(switchAndroid2OTA);
		FLog.d("【Switch Mode】DInput=>OTA CMD:" + text);
		SendByteArray(switchAndroid2OTA);
		return true;
	}

	public bool GetScreenInfo()
	{
		FLog.d("【DInput: GetScreenInfo】 :");
		SendByteArray(DongleCommand.getScreenStatusBarCmd());
		return true;
	}

	public bool SwitchMapConfig(byte status)
	{
		SendByteArray(DongleCommand.GetSwitchMapConfigCmd(status));
		return true;
	}

	public bool SwitchConfig(int ConfigId)
	{
		SendByteArray(DongleCommand.GetSwitchConfigCmd((byte)ConfigId));
		return true;
	}

	public bool Calibration(byte status)
	{
		SendByteArray(DongleCommand.GetCalibrationCmd(status));
		return true;
	}

	public bool ApplyScreenInfo(FDGDeviceScreenInfo fdgScreenInfo)
	{
		byte[] statusBarSetCommand = DongleCommand.getStatusBarSetCommand((byte)fdgScreenInfo.statusbarStatus);
		SendByteArray(statusBarSetCommand);
		return true;
	}

	public void ReadGamePadConfig(GamepadConfigReport gamepadConfigModel, bool isOnlyReadCfgID = false)
	{
		IsReading = false;
		IsOnlyReadCFGID = isOnlyReadCfgID;
		CurrentGamepadConfig = gamepadConfigModel;
		TempConfigListByte.Clear();
		TempConfigArrByte = new byte[(PackageLength + 1) * 10];
		if (!UsbDataManager.gFdgDeviceDic.ContainsKey(CurrentGamepadConfig.ReportId))
		{
			return;
		}
		try
		{
			byte[] readConfigCommand = DongleCommand.getReadConfigCommand(CurrentGamepadConfig.GamepadConfigId);
			FLog.d("Start ReadConfgIdCmd:" + DataUtils.ByteToHexString(readConfigCommand));
			if (UsbDataManager.gFdgDeviceDic[gamepadConfigModel.ReportId].DeviceId >= 0)
			{
				FLog.d("DInput: Start ReadGamePadConfig DeviceId:" + UsbDataManager.gFdgDeviceDic[gamepadConfigModel.ReportId].DeviceId + " CFG ID:" + CurrentGamepadConfig.GamepadConfigId);
				SendByteArray(readConfigCommand);
				TempConfigListByte.Clear();
				TempLEDConfigListByte.Clear();
			}
		}
		catch (Exception ex)
		{
			FLog.d("GetGamePadConfig Exception Message:" + ex.Message);
		}
	}

	public void ReadNewLedConfig(GamepadConfigReport gamepadConfigModel)
	{
		IsLEDReading = false;
		CurrentGamepadConfig = gamepadConfigModel;
		TempLEDConfigListByte.Clear();
		TempLEDConfigArrByte = new byte[(PackageLength + 1) * 10];
		if (!UsbDataManager.gFdgDeviceDic.ContainsKey(CurrentGamepadConfig.ReportId))
		{
			return;
		}
		try
		{
			byte[] readLEDConfigCommand = DongleCommand.getReadLEDConfigCommand(CurrentGamepadConfig.GamepadConfigId);
			FLog.d("Start Read LED ConfgId Cmd:" + DataUtils.ByteToHexString(readLEDConfigCommand));
			FLog.d("Start Read LED ConfgIdCmd:" + DataUtils.ByteToHexString(readLEDConfigCommand));
			if (UsbDataManager.gFdgDeviceDic[gamepadConfigModel.ReportId].DeviceId >= 0)
			{
				FLog.d("DInput: Start ReadGamePadConfig DeviceId:" + UsbDataManager.gFdgDeviceDic[gamepadConfigModel.ReportId].DeviceId + " LED  CFG ID:" + CurrentGamepadConfig.GamepadConfigId);
				IsLEDReading = true;
				SendByteArray(readLEDConfigCommand);
			}
		}
		catch (Exception ex)
		{
			FLog.d("GetGamePadConfig Exception Message:" + ex.Message);
		}
	}

	public void WriteGamePadConfig(List<List<byte>> list, IDelegateCallback writeConfigCallback, bool isFlash = false)
	{
		if (list.Count > 0 && list != null)
		{
			IsFlash = isFlash;
			WriteConfigCallback = writeConfigCallback;
			IsWriting = true;
			FullConfigList.Clear();
			FullConfigList.AddRange(list);
			FullPackageCount = FullConfigList.Count - 1;
			CurrentWPIndex = 0;
			FLog.d("Start To Write Config Info");
			ReadPackageId = 0;
			SendFullConfigDataPacket();
		}
	}

	public static async void WriteFlash(List<List<byte>> sendFlashByteList)
	{
		if (GetCurrentInstance().IsWriting)
		{
			return;
		}
		IsWriteFlash = true;
		GetCurrentInstance().WriteGamePadConfig(sendFlashByteList, (int result) =>
		{
			if (result == 100)
			{
				FLog.d("WriteFlash:" + result);
				IsWriteFlash = false;
			}
		}, isFlash: true);
	}

	public void HandleGamepadConfigReadCB(byte[] readBuffer)
	{
		int num = readBuffer[3];
		UpdateTempListByte(readBuffer);
		if (num == 0 && TempConfigListByte[0] == 1 && TempConfigListByte[1] == 3)
		{
			PackageLength = Constant.PackLengthNewV31;
		}
		FLog.d(string.Format("【DInput】Read Cfg ID:{0}- CallBack Length:{1} Index:{2} Receive Length:{3}", new object[4] { CurrentGamepadConfig.GamepadConfigId, PackageLength, num, TempConfigListByte.Count }));
		if (num != PackageLength)
		{
			return;
		}
		IsReading = false;
		if (TempConfigListByte.Count > 0 && CurrentGamepadConfig != null)
		{
			GamepadConfigBase.CurrentDeviceId = UsbDataManager.gFdgDeviceDic[ReportIndex].DeviceId;
			TempConfigListByte.Clear();
			TempConfigListByte = TempConfigArrByte.ToList();
			FLog.d("【Gamepad Config Read Complate:】data num:" + TempConfigListByte.Count);
			FLog.d("【Gamepad Config Read Complate:】data num:" + TempConfigListByte.Count);
			if (TempConfigListByte.Count >= 2)
			{
				UsbDataManager.CurrentConfigVersion = BitConverter.ToInt16(new byte[2]
				{
					TempConfigListByte[1],
					TempConfigListByte[0]
				}, 0);
			}
			if (TempConfigListByte[1] == 1)
			{
				CurrentGamepadConfig.ConfigBean = GamepadConfigUtilsV1.ConvertGPConfigByByte(TempConfigListByte);
			}
			else if (TempConfigListByte[1] == 2)
			{
				CurrentGamepadConfig.ConfigBean = GamepadConfigUtilsV2.ConvertGPConfigByByte(TempConfigListByte);
			}
			else if (TempConfigListByte[1] == 3)
			{
				CurrentGamepadConfig.ConfigBean = GamepadConfigUtilsV3.ConvertGPConfigByByte(TempConfigListByte);
			}
			if (CurrentGamepadConfig.ConfigBean != null)
			{
				if (GamePadVersionUtils.IsSupportNewLedConfig(UsbDataManager.gFdgDeviceDic[ReportIndex]))
				{
					Task.Delay(50).ContinueWith((Task t) =>
					{
						ReadNewLedConfig(CurrentGamepadConfig);
					});
				}
				else
				{
					if (IsOnlyReadCFGID)
					{
						GamepadConfigNotice.ReadConfigOnlyCFGIDCB(CurrentGamepadConfig);
					}
					else
					{
						GamepadConfigNotice.ReadConfigCB(CurrentGamepadConfig);
					}
					TempConfigListByte.Clear();
				}
			}
		}
		FLog.d("Config Info is read Finished");
	}

	public void HandleLEDConfigReadCB(byte[] readBuffer)
	{
		int num = readBuffer[3];
		UpdateLEDTempListByte(readBuffer);
		if (!IsLEDReading)
		{
			return;
		}
		FLog.d(string.Format("【DInput】Read LED Cfg ID:{0}- CallBack Length:{1} Index:{2} Receive Length:{3} ", new object[4] { CurrentGamepadConfig.GamepadConfigId, PackageLength, num, TempLEDConfigListByte.Count }));
		if (num != LEDPackageLength)
		{
			return;
		}
		IsLEDReading = false;
		if (TempLEDConfigListByte.Count > 0 && CurrentGamepadConfig != null)
		{
			GamepadConfigBase.CurrentDeviceId = UsbDataManager.gFdgDeviceDic[ReportIndex].DeviceId;
			TempLEDConfigListByte.Clear();
			TempLEDConfigListByte = TempLEDConfigArrByte.ToList();
			FLog.d("【Gamepad Config Read Complate:】data num:" + TempLEDConfigListByte.Count);
			FLog.d("【Gamepad Config Read Complate:】data num:" + TempLEDConfigListByte.Count);
			CurrentGamepadConfig.ConfigBean.Basic.NewLedConfig = GamepadConfigUtilsV2.ConvertLEDConfigByByte(TempLEDConfigListByte);
			if (CurrentGamepadConfig.ConfigBean != null)
			{
				GamepadConfigNotice.ReadConfigCB(CurrentGamepadConfig);
				TempLEDConfigListByte.Clear();
			}
		}
		FLog.d("Config Info is read Finished");
	}

	public async void HandleGamePadInfo(byte[] readBuffer)
	{
		UsbDataManager.retries = 0;
		UsbDataManager.cts?.Cancel();
		byte[] reportBuff = eReport.reportBuff;
		FDGDeviceInfo currentDeviceInfo = GetCurrentDeviceInfo(eReport.reportID);
		if (currentDeviceInfo == null || currentDeviceInfo.DeviceId > 0)
		{
			return;
		}
		byte b = (byte)(currentDeviceInfo.DeviceId = reportBuff[3]);
		currentDeviceInfo.DeviceIdInFlash = b;
		if (!GameHandleListDic.gameHandleDic.ContainsKey(currentDeviceInfo.DeviceId))
		{
			currentDeviceInfo.UpdateDeviceIdByDeviceInfo();
		}
		if (currentDeviceInfo.DeviceId <= 0)
		{
			return;
		}
		byte[] deviceMac = new byte[4]
		{
			reportBuff[5],
			reportBuff[6],
			reportBuff[7],
			reportBuff[8]
		};
		byte[] deviceMac2 = new byte[4]
		{
			reportBuff[8],
			reportBuff[7],
			reportBuff[6],
			reportBuff[5]
		};
		currentDeviceInfo.DeviceMac = DataUtils.ByteToHexStringNew(deviceMac).Trim(new char[1] { ':' });
		currentDeviceInfo.DeviceMacFixed = DataUtils.ByteToHexStringNew(deviceMac2).Trim(new char[1] { ':' });
		currentDeviceInfo.GameHadleName = GameHandleListDic.gameHandleDic[b].GameHadleName;
		currentDeviceInfo.FirmwareName = GameHandleListDic.gameHandleDic[b].FirmwareName;
		int num2 = reportBuff[9] & 0xF;
		int num3 = reportBuff[9] >> 4;
		int num4 = reportBuff[10] & 0xF;
		int num5 = reportBuff[10] >> 4;
		currentDeviceInfo.FirmwareVersionCode = num5 * 1000 + num4 * 100 + num3 * 10 + num2;
		currentDeviceInfo.FirmwareVersion = num5 + "." + num4 + "." + num3 + "." + num2;
		int num6 = reportBuff[11];
		int num7 = 98;
		int num8 = 114;
		if (num6 < num7)
		{
			num6 = num7;
		}
		else if (num6 > num8)
		{
			num6 = num8;
		}
		int batteryPercent = (int)((float)(num6 - num7) / (float)(num8 - num7) * 100f);
		currentDeviceInfo.BatteryPercent = batteryPercent;
		if (reportBuff[14] == 1)
		{
			currentDeviceInfo.MotionSensorType = "ST";
		}
		else if (reportBuff[14] == 2)
		{
			currentDeviceInfo.MotionSensorType = "QST";
		}
		if ((reportBuff[12] & 0xFF) > 0)
		{
			currentDeviceInfo.CpuType = "wch";
		}
		else
		{
			currentDeviceInfo.CpuType = "nordic";
		}
		if (num5 >= 6 && num4 >= 1)
		{
			currentDeviceInfo.CpuType = "wch";
		}
		if (currentDeviceInfo.CpuType == "wch")
		{
			if ((reportBuff[13] & 0xFF) == 1)
			{
				currentDeviceInfo.ConnectType = FDGConncetType.wired;
				currentDeviceInfo.CpuName = "ch573";
			}
			else
			{
				currentDeviceInfo.ConnectType = FDGConncetType.wireless;
				currentDeviceInfo.CpuName = "ch571";
				FLog.d("getDongleVersionCommand:");
				GetDongleInfo();
			}
		}
		currentDeviceInfo.GameHadleName = GameHandleListDic.gameHandleDic[currentDeviceInfo.DeviceId].GameHadleName;
		currentDeviceInfo.ShowGameHadleName = GameHandleListDic.gameHandleDic[currentDeviceInfo.DeviceId].ShowGameHadleName;
		currentDeviceInfo.FirmwareName = GameHandleListDic.gameHandleDic[currentDeviceInfo.DeviceId].FirmwareName;
		currentDeviceInfo.DONGLEFirmwareName = GameHandleListDic.gameHandleDic[currentDeviceInfo.DeviceId].DONGLEFirmwareName;
		currentDeviceInfo.SIFirmwareVersion = GameHandleListDic.gameHandleDic[currentDeviceInfo.DeviceId].SIFirmwareVersion;
		currentDeviceInfo.ResName = GameHandleListDic.gameHandleDic[currentDeviceInfo.DeviceId].ResName;
		currentDeviceInfo.IsIP = GameHandleListDic.gameHandleDic[currentDeviceInfo.DeviceId].IsIP;
		currentDeviceInfo.ThemeBgColor = GameHandleListDic.gameHandleDic[currentDeviceInfo.DeviceId].ThemeBgColor;
		currentDeviceInfo.ThemeFrColor = GameHandleListDic.gameHandleDic[currentDeviceInfo.DeviceId].ThemeFrColor;
		currentDeviceInfo.ThemeFrHoverColor = GameHandleListDic.gameHandleDic[currentDeviceInfo.DeviceId].ThemeFrHoverColor;
		currentDeviceInfo.LedNum = GameHandleListDic.gameHandleDic[currentDeviceInfo.DeviceId].LedNum;
		currentDeviceInfo.LcdFirmwareName = GameHandleListDic.gameHandleDic[currentDeviceInfo.DeviceId].LcdFirmwareName;
		currentDeviceInfo.TriggerFirmwareName = GameHandleListDic.gameHandleDic[currentDeviceInfo.DeviceId].TriggerFirmwareName;
		switch (currentDeviceInfo.DeviceId)
		{
		case 19:
			currentDeviceInfo.FirmwareName = "apex2";
			break;
		case 20:
		case 21:
			currentDeviceInfo.FirmwareName = "f1";
			if (currentDeviceInfo.CpuType == "wch")
			{
				currentDeviceInfo.FirmwareName = "f1wch";
			}
			break;
		case 23:
			currentDeviceInfo.FirmwareName = "f1p";
			break;
		case 22:
			currentDeviceInfo.FirmwareName = "f1p";
			break;
		case 24:
			currentDeviceInfo.FirmwareName = "k1";
			break;
		case 25:
			currentDeviceInfo.FirmwareName = "fp1";
			break;
		case 28:
		case 80:
		case 81:
		case 88:
			UsbDataManager.MaxRetryNum = 3;
			break;
		case 102:
			UsbDataManager.MaxRetryNum = 30;
			break;
		default:
			UsbDataManager.MaxRetryNum = 0;
			break;
		}
		currentDeviceInfo.SelCfgId = readBuffer[4];
		currentDeviceInfo.Keys = GamePadHelper.GetKeysByDeviceId(b);
		if (currentDeviceInfo.DeviceId > 0)
		{
			GamePadVersionUtils.UpdageGamepadConfigInfo(currentDeviceInfo);
			PackageLength = (byte)currentDeviceInfo.PackageLength;
		}
		bool flag = false;
		if (GamePadVersionUtils.IsNeedGetExtChipInfo(currentDeviceInfo) && currentDeviceInfo.ExtChipInfo == null)
		{
			flag = true;
			byte[] k1ExtensionChipInfo = DongleCommand.getK1ExtensionChipInfo();
			string cmdKeyV = GetCmdKeyV3(k1ExtensionChipInfo);
			UsbDataManager._ackCmdFlags[cmdKeyV] = false;
			SendByteArray(k1ExtensionChipInfo);
		}
		if (GamePadVersionUtils.IsSupportSI(currentDeviceInfo) && currentDeviceInfo.ExtChipInfo == null && !flag)
		{
			byte[] k1ExtensionChipInfo2 = DongleCommand.getK1ExtensionChipInfo();
			string cmdKeyV2 = GetCmdKeyV3(k1ExtensionChipInfo2);
			UsbDataManager._ackCmdFlags[cmdKeyV2] = false;
			SendByteArray(k1ExtensionChipInfo2);
		}
		ReadGamepadConfigId();
		if (currentDeviceInfo.ConnectType == FDGConncetType.wired && GamePadVersionUtils.IsFuncSupport(currentDeviceInfo) && currentDeviceInfo.DeviceId > 0)
		{
			GamepadInfoNotice.ReadGamepadInfoCB();
		}
		FLog.d("DInput hander deviceInfo gFdgDeviceDic:" + JsonConvert.SerializeObject(UsbDataManager.gFdgDeviceDic));
		UsbDataManager.FDGDeviceInfo = currentDeviceInfo;
		KeyCountService.InitData(UsbDataManager.FDGDeviceInfo.DeviceMac);
		GamepadMonitorCenter.ReStartModService();
	}

	public void ReadGamepadConfigId()
	{
		IsActiveReadCFGID = true;
		SendByteArray(DongleCommand.getCurrentConfigIdCommand());
	}

	public void HandleGamepadConfigId(byte[] readBuffer)
	{
		FDGDeviceInfo currentDeviceInfo = GetCurrentDeviceInfo(eReport.reportID);
		if (currentDeviceInfo != null)
		{
			currentDeviceInfo.SelCfgId = readBuffer[5];
			currentDeviceInfo.SelSwitchCfgId = 4;
			if (readBuffer[6] == 160)
			{
				currentDeviceInfo.SelSwitchCfgId = readBuffer[7];
			}
			if (IsActiveReadCFGID)
			{
				IsActiveReadCFGID = false;
				GamepadInfoNotice.ActiveReadGamepadIdCB();
			}
			else
			{
				GamepadInfoNotice.ReadOrSwitchGamepadIdCB();
			}
		}
	}

	public void HanderExtensionChipInfo(byte[] data)
	{
		FDGDeviceInfo currentDeviceInfo = GetCurrentDeviceInfo(eReport.reportID);
		if (currentDeviceInfo != null)
		{
			int num = 0;
			int num2 = 0;
			int num3 = 0;
			int num4 = 0;
			int num5 = 0;
			int num6 = 0;
			int num7 = 0;
			int num8 = 0;
			int num9 = 0;
			int num10 = 0;
			int num11 = 0;
			int num12 = 0;
			FDGDeviceExtChipInfo extChipInfo = GetExtChipInfo();
			if (Enumerable.Contains(GamePadVersionUtils.K2Serial, currentDeviceInfo.DeviceId))
			{
				num2 = data[5] & 0xF0;
				num = data[5] & 0xF;
				num3 = data[6] & 0xF;
				num4 = data[6] >> 4;
				num5 = data[7] & 0xF0;
				num6 = data[7] & 0xF;
				num7 = data[8] & 0xF;
				num8 = data[8] >> 4;
				num9 = data[9] & 0xF0;
				num10 = data[9] & 0xF;
				num11 = data[10] & 0xF;
				num12 = data[10] >> 4;
				extChipInfo.ExtCpuVerion = num2 + "." + num + "." + num4 + "." + num3;
				extChipInfo.LcdVersion = num5 + "." + num6 + "." + num8 + "." + num7;
				extChipInfo.SwitchExtCpuVersion = num9 + "." + num10 + "." + num12 + "." + num11;
			}
			else
			{
				num = data[5];
				num3 = data[6] & 0xF;
				num4 = data[6] >> 4;
				num6 = data[7];
				num7 = data[8] & 0xF;
				num8 = data[8] >> 4;
				num9 = data[9] & 0xF;
				num10 = data[9] >> 4;
				num11 = data[10] & 0xF;
				num12 = data[10] >> 4;
				extChipInfo.ExtCpuVerion = num + "." + num4 + "." + num3;
				extChipInfo.LcdVersion = num6 + "." + num8 + "." + num7;
				extChipInfo.SwitchExtCpuVersion = num10 + "." + num9 + "." + num12 + "." + num11;
			}
			byte b = data[11];
			_ = data[12];
			byte b2 = data[13];
			byte b3 = data[14];
			int versionNumber = (b << 8) | b;
			extChipInfo.PYVersion = DataUtils.FormateVersion(versionNumber);
			versionNumber = (b2 << 8) | b3;
			extChipInfo.Bs21Version = DataUtils.FormateVersion(versionNumber);
			currentDeviceInfo.ExtChipInfo = extChipInfo;
			GamepadInfoNotice.NotifyGamepadInfoUpdate();
		}
	}

	public FDGDeviceExtChipInfo GetExtChipInfo()
	{
		if (mFDGExtChipInfo == null)
		{
			mFDGExtChipInfo = new FDGDeviceExtChipInfo();
		}
		return mFDGExtChipInfo;
	}

	public void HanderScreenInfoSleepTime(byte[] readBuffer)
	{
		FDGDeviceInfo currentDeviceInfo = GetCurrentDeviceInfo(eReport.reportID);
		if (currentDeviceInfo != null)
		{
			if (currentDeviceInfo.ScreenInfo == null)
			{
				currentDeviceInfo.ScreenInfo = new FDGDeviceScreenInfo();
			}
			currentDeviceInfo.ScreenInfo.sleepTime = readBuffer[5];
			currentDeviceInfo.ScreenInfo.isSwitch = readBuffer[6] == 1;
			if (readBuffer[5] == byte.MaxValue)
			{
				currentDeviceInfo.ScreenInfo.sleepTime = 15;
			}
			GamepadInfoNotice.GetSleepTimeCB(JsonConvert.SerializeObject(currentDeviceInfo));
		}
	}

	public void HanderScreenInfo(byte[] readBuffer)
	{
		FDGDeviceInfo currentDeviceInfo = GetCurrentDeviceInfo(eReport.reportID);
		if (currentDeviceInfo != null)
		{
			if (currentDeviceInfo.ScreenInfo == null)
			{
				currentDeviceInfo.ScreenInfo = new FDGDeviceScreenInfo();
			}
			currentDeviceInfo.ScreenInfo.statusbarStatus = readBuffer[5];
			currentDeviceInfo.ScreenInfo.resourceStatus = readBuffer[6];
			ScreenInfoReport screenInfoReport = new ScreenInfoReport();
			screenInfoReport.ReportId = ReportIndex;
			screenInfoReport.ScreenInfo = currentDeviceInfo.ScreenInfo;
			FDGProtocolService.PostMessage(13, JsonConvert.SerializeObject(screenInfoReport));
		}
	}

	public void HandleDongleInfo(byte[] readBuffer)
	{
		UsbDataManager.retries = 0;
		UsbDataManager.dongle_cts?.Cancel();
		FDGDeviceInfo currentDeviceInfo = GetCurrentDeviceInfo(eReport.reportID);
		if (currentDeviceInfo != null)
		{
			byte b = readBuffer[2];
			byte b2 = readBuffer[3];
			int num = b & 0xF;
			int num2 = b >> 4;
			int num3 = b2 & 0xF;
			int num4 = b2 >> 4;
			if (num + num2 + num3 + num4 > 0)
			{
				currentDeviceInfo.DongleVersion = num2 + "." + num + "." + num4 + "." + num3;
				currentDeviceInfo.ConnectType = FDGConncetType.wireless;
				FLog.d("xinput dongle Version :" + currentDeviceInfo.DongleVersion);
			}
			else
			{
				currentDeviceInfo.ConnectType = FDGConncetType.wired;
			}
			if (GamePadVersionUtils.IsFuncSupport(currentDeviceInfo) && currentDeviceInfo.DeviceId > 0)
			{
				GamepadInfoNotice.ReadGamepadInfoCB();
			}
			FLog.d("HandleDongleInfo:3");
		}
	}

	public void HandleK1TriggerInfo(byte[] readBuffer)
	{
	}

	public void HandleStartWriteGamepadConfig()
	{
	}

	public void HandleWriteGamepadConfigCBK(byte[] readBuffer)
	{
		if (WriteConfigCallback == null)
		{
			return;
		}
		UsbDataManager.retries = 0;
		UsbDataManager.cts?.Cancel();
		ReadPackageId = readBuffer[3];
		FLog.d("HandleWriteGamepadConfigCBK:" + ReadPackageId + "_CurrentWPIndex_" + CurrentWPIndex + "___FullPackageCount:" + FullPackageCount);
		if (ReadPackageId < CurrentWPIndex)
		{
			return;
		}
		CurrentWPIndex++;
		int num = FullPackageCount - 1;
		if (CurrentWPIndex > num)
		{
			FLog.d("HandleWriteGamepadConfigCBK1:" + ReadPackageId + "_CurrentWPIndex_" + CurrentWPIndex + "___PackageCount:" + num);
			if (ReadPackageId == num)
			{
				FLog.d("Write Config packageIndex end:" + CurrentWPIndex);
				SendByteArray(FullConfigList[CurrentWPIndex].ToArray());
			}
			FullConfigList.Clear();
			CurrentWPIndex = 0;
			IsWriting = false;
			if (ReadPackageId == num)
			{
				WriteConfigCallback(100);
			}
		}
		else
		{
			FLog.d("HandleWriteGamepadConfigCBK2:" + ReadPackageId + "_CurrentWPIndex_" + CurrentWPIndex + "___PackageCount:" + num);
			SendFullConfigDataPacket();
		}
	}

	private void SendFullConfigDataPacket()
	{
		if (CurrentWPIndex >= FullConfigList.Count)
		{
			return;
		}
		FLog.d("SendDataPacket Config package Index:" + CurrentWPIndex);
		FLog.d($"【SendDataPacket】 Config package Index:【{CurrentWPIndex}】");
		currentIndex = CurrentWPIndex;
		FLog.d($"DInput Config Send Config Data:【ReadPackageId:{ReadPackageId}】 【FullPackageCount:{FullPackageCount}】【CurrentWPIndex:{CurrentWPIndex}】");
		SendByteArray(FullConfigList[CurrentWPIndex].ToArray());
		UsbDataManager.cts = new CancellationTokenSource();
		Task.Delay(UsbDataManager.RetrayDelayCheckTime, UsbDataManager.cts.Token).ContinueWith((Task t) =>
		{
			if (!t.IsCanceled)
			{
				ResendDataPacket();
			}
		});
	}

	private void ResendDataPacket()
	{
		FLog.d($"【ResendDataPacket----】:{UsbDataManager.retries}__currentIndex:{currentIndex}___CurrentWPIndex:{CurrentWPIndex}");
		FLog.d($"【ResendDataPacket0】:{UsbDataManager.retries}");
		if (UsbDataManager.retries < UsbDataManager.MaxRetryGamepadInfoNum && currentIndex == CurrentWPIndex)
		{
			FLog.d($"【ResendDataPacket----ReSend】times:{UsbDataManager.retries}_CurrentWPIndex:{CurrentWPIndex}");
			FLog.d($"【ResendDataPacket----ReSend】:{UsbDataManager.retries}");
			UsbDataManager.retries++;
			SendFullConfigDataPacket();
		}
	}

	public void UpdateTempListByte(byte[] readBuffer)
	{
		int num = readBuffer[3];
		if (num > PackageLength)
		{
			return;
		}
		List<byte> realByteFromCallback = DInputDataUtils.GetRealByteFromCallback(readBuffer);
		try
		{
			for (int i = 0; i < realByteFromCallback.Count; i++)
			{
				TempConfigListByte.Add(realByteFromCallback[i]);
				TempConfigArrByte[num * 10 + i] = realByteFromCallback[i];
			}
		}
		catch (Exception ex)
		{
			FLog.d("Update Temp Config List Exception Msg:" + ex.Message);
		}
	}

	public void UpdateLEDTempListByte(byte[] readBuffer)
	{
		int num = readBuffer[3];
		if (num > LEDPackageLength)
		{
			return;
		}
		List<byte> realByteFromCallback = DInputDataUtils.GetRealByteFromCallback(readBuffer);
		try
		{
			for (int i = 0; i < realByteFromCallback.Count; i++)
			{
				TempLEDConfigListByte.Add(realByteFromCallback[i]);
				TempLEDConfigArrByte[num * 10 + i] = realByteFromCallback[i];
			}
		}
		catch (Exception ex)
		{
			FLog.d("Update Temp LED Config List Exception Msg:" + ex.Message);
		}
	}

	public void UpdateFDGInfo(int reportIndex, FDGDeviceInfo fdgDeviceInfo)
	{
		ReportIndex = reportIndex;
		if (!UsbDataManager.gFdgDeviceDic.ContainsKey(reportIndex))
		{
			UsbDataManager.gFdgDeviceDic.Add(ReportIndex, fdgDeviceInfo);
			UsbDataManager.retries = 0;
			GetDeviceInfo();
		}
	}

	public static async void BuildDataAndWrite(FDGDeviceInfo fdgDeviceInfo, GamepadConfigReport gamepadConfigModel)
	{
		bool IsApplySuccessed = false;
		IsSuccessNotify = false;
		ConfigApplier configApplier = new ConfigApplier();
		ConfigApplier.SetIsApplySuccessed(IsSuccessNotify);
		ConfigApplier._cts?.Cancel();
		List<byte> list = null;
		List<List<byte>> sendWriteFullData = null;
		List<byte> list2 = new List<byte>();
		List<List<byte>> ExtSendWriteFullData = new List<List<byte>>();
		new List<byte>();
		List<List<byte>> LEDSendWriteFullData = new List<List<byte>>();
		IsSuccessNotify = false;
		FLog.d("DInputBuildDataWrite:0");
		if (GetCurrentInstance().IsWriting)
		{
			GamepadConfigNotice.ApplyConfigResultCB(IsApplySuccessed);
			FLog.d("DInputBuildDataWrite:1");
			return;
		}
		if (gamepadConfigModel == null && gamepadConfigModel.ConfigBean == null)
		{
			FLog.d("DInputBuildDataWrite:2");
			GamepadConfigNotice.ApplyConfigResultCB(IsApplySuccessed);
			return;
		}
		try
		{
			FLog.d("DInputBuildDataWrite:3");
			FLog.d("fdgDeviceInfo ConfigVersion" + fdgDeviceInfo.ConfigVersion);
			if (fdgDeviceInfo.ConfigVersion == 1)
			{
				list = GamepadConfigUtilsV1.ConvertByteByGPConfig(gamepadConfigModel.ConfigBean);
			}
			else if (fdgDeviceInfo.ConfigVersion == 2)
			{
				list = GamepadConfigUtilsV2.ConvertByteByGPConfig(gamepadConfigModel.ConfigBean);
			}
			else if (fdgDeviceInfo.ConfigVersion == 3)
			{
				list = GamepadConfigUtilsV3.ConvertByteByGPConfig(gamepadConfigModel.ConfigBean);
			}
			FLog.d("start write Data ConfigBean:" + JsonConvert.SerializeObject(gamepadConfigModel.ConfigBean));
			FLog.d("start write Data configDataList num:" + list.Count);
			sendWriteFullData = DInputDataUtils.FormatterWriteFullData(list.ToArray(), (byte)gamepadConfigModel.GamepadConfigId);
			if (GamePadVersionUtils.IsSupportAutoTrigger(fdgDeviceInfo.DeviceId) && GamePadVersionUtils.IsSupportTriggerVibration(fdgDeviceInfo) && fdgDeviceInfo.ConfigVersion == 1)
			{
				list2 = GamepadConfigUtilsV1.GetExtFullConfigListByConfig(gamepadConfigModel.ConfigBean);
				if (list2.Count > 0)
				{
					ExtSendWriteFullData = DInputDataUtils.GetExtConfigListByConfig(list2);
				}
			}
			if (GamePadVersionUtils.IsSupportNewLedConfig(fdgDeviceInfo))
			{
				List<byte> list3 = GamepadConfigUtilsV2.ConvertByteByLedConfig(gamepadConfigModel.ConfigBean);
				FLog.d("LEDConfigDataList count:" + list3.Count);
				LEDSendWriteFullData = DInputDataUtils.FormatterWriteFullLEDData(list3.ToArray(), (byte)gamepadConfigModel.GamepadConfigId);
			}
			for (int i = 0; i < sendWriteFullData.Count; i++)
			{
				FLog.d("D配置列表页-配置写入待发送配置  CONFIG:" + DataUtils.ByteToHexString(sendWriteFullData[i].ToArray()));
				FLog.d("D配置列表页-配置写入待发送配置 CONFIG:" + DataUtils.ByteToHexString(sendWriteFullData[i].ToArray()));
			}
			for (int j = 0; j < ExtSendWriteFullData.Count; j++)
			{
				FLog.d("D配置列表页-配置写入待发送配置 扩展配置:" + DataUtils.ByteToHexString(ExtSendWriteFullData[j].ToArray()));
				FLog.d("D配置列表页-配置写入待发送配置 扩展配置:" + DataUtils.ByteToHexString(ExtSendWriteFullData[j].ToArray()));
			}
			for (int k = 0; k < LEDSendWriteFullData.Count; k++)
			{
				FLog.d("D配置列表页-配置写入待发送配置 LED灯光:" + DataUtils.ByteToHexString(LEDSendWriteFullData[k].ToArray()));
				FLog.d("D配置列表页-配置写入待发送配置 LED灯光:" + DataUtils.ByteToHexString(LEDSendWriteFullData[k].ToArray()));
			}
			CancellationTokenSource _cts = new CancellationTokenSource();
			if (list2.Count > 0)
			{
				configApplier.writeConfigTask = Task.Run(() =>
				{
					FLog.d("Dinput start send data ,package length:" + sendWriteFullData.Count);
					GetCurrentInstance().WriteGamePadConfig(sendWriteFullData, (int result) =>
					{
						if (result == 100)
						{
							FLog.d("Dinput start send EXT data ,package length:" + ExtSendWriteFullData.Count);
							GetCurrentInstance().WriteGamePadConfig(ExtSendWriteFullData, (int extResult) =>
							{
								if (extResult == 100)
								{
									IsApplySuccessed = true;
									if (!IsSuccessNotify)
									{
										IsSuccessNotify = true;
										ConfigApplier.SetIsApplySuccessed(IsSuccessNotify);
										GamepadConfigNotice.ApplyConfigResultCB(IsApplySuccessed);
										FLog.d("【gamepadConfigModel CB】  CFGID:" + gamepadConfigModel.GamepadConfigId);
									}
								}
							});
						}
					});
				}, _cts.Token);
			}
			else
			{
				configApplier.writeConfigTask = Task.Run(() =>
				{
					FLog.d("Dinput start send Config  data ,package length:" + sendWriteFullData.Count);
					GetCurrentInstance().WriteGamePadConfig(sendWriteFullData, async (int result) =>
					{
						if (result == 100)
						{
							FLog.d("Dinput start send Led data ,package length:" + LEDSendWriteFullData.Count);
							if (LEDSendWriteFullData.Count > 0)
							{
								if (!ConfigApplier.IsSuccessNotify)
								{
									await Task.Delay(500);
									GetCurrentInstance().WriteGamePadConfig(LEDSendWriteFullData, (int num) =>
									{
										if (num == 100)
										{
											IsApplySuccessed = true;
											if (!IsSuccessNotify)
											{
												IsSuccessNotify = true;
												ConfigApplier.SetIsApplySuccessed(IsSuccessNotify);
												GamepadConfigNotice.ApplyConfigResultCB(IsApplySuccessed);
												FLog.d("【gamepadConfigModel CB】  CFGID:" + gamepadConfigModel.GamepadConfigId);
											}
										}
									});
								}
							}
							else
							{
								IsApplySuccessed = true;
								if (!IsSuccessNotify)
								{
									IsSuccessNotify = true;
									ConfigApplier.SetIsApplySuccessed(IsSuccessNotify);
									GamepadConfigNotice.ApplyConfigResultCB(IsApplySuccessed);
								}
							}
						}
					});
				}, _cts.Token);
			}
			await configApplier.ApplyConfigAsync();
			_cts?.Cancel();
		}
		catch (Exception ex)
		{
			FLog.d("write config exception:" + ex.Message + " stackTrace:" + ex.StackTrace);
		}
	}

	public void HandlerUUIDCB(byte[] readBuffer)
	{
		GamepadUUIDReport gamepadUUIDReport = new GamepadUUIDReport();
		int num = 4;
		if (readBuffer.Count() >= 16)
		{
			byte[] bytes = new byte[10]
			{
				readBuffer[num + 1],
				readBuffer[num + 2],
				readBuffer[num + 3],
				readBuffer[num + 4],
				readBuffer[num + 5],
				readBuffer[num + 6],
				readBuffer[num + 7],
				readBuffer[num + 8],
				readBuffer[num + 9],
				readBuffer[num + 10]
			};
			gamepadUUIDReport.uuid = DataUtils.BytesToHexString(bytes);
			GamepadInfoNotice.GetUUIDCB(JsonConvert.SerializeObject(gamepadUUIDReport));
		}
	}

	public bool SendByteArray(byte[] data)
	{
		FLog.d($"DInputsssss111111[RID:{ReportIndex}]: Send To Dongle Length->>：" + data.Length + ",CMD------>>" + DataUtils.ByteToHexString(data) + " Length:" + HID.gDeviceStreamList.Count);
		foreach (KeyValuePair<int, DeviceStream> gDeviceStream in HID.gDeviceStreamList)
		{
			FLog.d("HID.gDeviceStreamList Key" + gDeviceStream.Key);
		}
		if (!HID.gDeviceStreamList.ContainsKey(ReportIndex))
		{
			FLog.d($"DInputsssss2222222[RID:{ReportIndex}]: Send To Dongle Length->>：" + data.Length + ",CMD------>>" + DataUtils.ByteToHexString(data));
			return false;
		}
		try
		{
			DeviceStream deviceStream = HID.gDeviceStreamList[ReportIndex];
			if (deviceStream != null)
			{
				new StateObject
				{
					reportId = eReport.reportID,
					hidStream = deviceStream
				};
				deviceStream.WriteAsync(data, 0, data.Length);
			}
		}
		catch (Exception ex)
		{
			FLog.d("BeginAsyncReadNew exception:" + ex.Message + " stack trace:" + ex.StackTrace);
		}
		return true;
	}
}
