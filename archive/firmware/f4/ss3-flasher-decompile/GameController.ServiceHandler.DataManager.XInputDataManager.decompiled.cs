using System;
using System.Collections.Generic;
using System.Linq;
using System.Runtime.InteropServices;
using System.Threading;
using System.Threading.Tasks;
using GameController.ServiceHandler.Service;
using GameController.ServiceHandler.Service.Module;
using GameController.ServiceHandler.Service.Protocol;
using LibCommon.Command;
using LibCommon.Common.Delegate;
using LibCommon.Config;
using LibCommon.Model;
using LibCommon.Model.Game;
using LibCommon.Model.ProtocolModel;
using LibCommon.Services.Data;
using LibCommon.Services.Driver;
using LibCommon.Utils;
using Newtonsoft.Json;

namespace GameController.ServiceHandler.DataManager;

public class XInputDataManager : UsbDataManager, IUsbDataManager
{
	public const int StartByte = 16;

	public static byte PackageLength = Constant.PackLength;

	public static byte LedPackageLength = Constant.LedPackLengthNew;

	public static GamepadConfigReport CurrentGamepadConfig;

	public static XInputDataManager currentInstance;

	private static int FullPackageCount;

	private static int ReadPackageId = -1;

	public static bool IsReading;

	public static bool IsLEDReading;

	private static bool IsStartSend;

	private static bool IsSuccessNotify;

	private readonly List<List<byte>> FullConfigList = new List<List<byte>>();

	private int currentIndex;

	private int CurrentWPIndex;

	public bool IsActiveReadCFGID;

	public bool IsOnlyReadCFGID;

	public bool IsWriting;

	public byte[] LastXinputBuffer = new byte[32];

	public byte[] LastPicBuffer = new byte[32];

	private FDGDeviceExtChipInfo mFDGExtChipInfo;

	public byte[,] TempConfigArrByte = new byte[PackageLength, 10];

	public List<byte> TempConfigListByte = new List<byte>();

	public byte[,] TempLedConfigArrayByte = new byte[LedPackageLength + 1, 10];

	public List<byte> TempLedConfigListByte = new List<byte>();

	private IDelegateCallback WriteConfigCallback;

	public static bool IsWriteFlash = false;

	public static bool IsWriteFlashSuccess = false;

	public static bool IsWriteFlashLedSuccess = false;

	public void UpdateFDGInfo(int reportIndex, FDGDeviceInfo fdgDeviceInfo)
	{
		AddFDgInfo(reportIndex, fdgDeviceInfo);
		UsbDataManager.retries = 0;
	}

	public void AddFDgInfo(int reportIndex, FDGDeviceInfo fdgDeviceInfo)
	{
		UsbDataManager.ReportIndex = reportIndex;
		if (!UsbDataManager.gFdgDeviceDic.ContainsKey(reportIndex))
		{
			FLog.d("Before reportIndex:" + UsbDataManager.ReportIndex + " info:" + JsonConvert.SerializeObject(UsbDataManager.gFdgDeviceDic));
			UsbDataManager.gFdgDeviceDic.Add(UsbDataManager.ReportIndex, fdgDeviceInfo);
			FLog.d("After reportIndex:" + UsbDataManager.ReportIndex + " info:" + JsonConvert.SerializeObject(UsbDataManager.gFdgDeviceDic));
			if (UsbDataManager.gFdgDeviceDic[UsbDataManager.ReportIndex].DeviceId < 0)
			{
				GetDeviceInfo();
			}
		}
		else
		{
			FLog.d("After reportIndex:" + UsbDataManager.ReportIndex + " info:" + JsonConvert.SerializeObject(UsbDataManager.gFdgDeviceDic));
		}
	}

	public void ResolveUsbData(byte[] readBuffer)
	{
		if (readBuffer[14] == 90 && readBuffer[15] == 165)
		{
			if (LastPicBuffer == null || !Enumerable.SequenceEqual(LastPicBuffer, readBuffer))
			{
				LastPicBuffer = readBuffer;
				switch (readBuffer[16])
				{
				case 208:
				case 209:
					DataUtils.ByteToHexString(readBuffer);
					ScreenDataTransService.HandlerPicData(84, readBuffer[18], readBuffer[19], readBuffer[20]);
					break;
				case 210:
				case 211:
					ScreenDataTransService.CloseStream(UsbDataManager.FDGDeviceInfo);
					ScreenDataTransService.HandlerPicTransferResult(84, readBuffer[16], readBuffer[18], readBuffer[20]);
					break;
				}
			}
			return;
		}
		LastPicBuffer = null;
		if (readBuffer[14] != 165)
		{
			if (UsbDataManager.IsListenOperationData)
			{
				byte[] buffer = DataUtils.XInputFormatOperateEventData(readBuffer);
				InvokeUsbData(buffer);
			}
			else if (UsbDataManager.IsListenMappingData && readBuffer[0] == 0 && readBuffer[1] == 20)
			{
				byte[] buffer2 = DataUtils.XInputFormatMapingData(readBuffer);
				InvokeUsbMappingData(buffer2);
			}
			string text = CommonUtils.byteToHexString(DataUtils.XInputFormatOperateEventData(readBuffer));
			if (!string.IsNullOrEmpty(text))
			{
				try
				{
					KeyCountService.RecordQueue.Enqueue(text);
				}
				catch (Exception)
				{
				}
			}
		}
		if ((UsbDataManager.FDGDeviceInfo != null && Enumerable.SequenceEqual(LastXinputBuffer, readBuffer) && (GamePadVersionUtils.IsF3Serial(UsbDataManager.FDGDeviceInfo) || GamePadVersionUtils.IsFP3Serial(UsbDataManager.FDGDeviceInfo) || GamePadVersionUtils.IsFP4Serial(UsbDataManager.FDGDeviceInfo))) || (UsbDataManager.FDGDeviceInfo != null && GamePadVersionUtils.IsF4Serial(UsbDataManager.FDGDeviceInfo) && Enumerable.SequenceEqual(LastXinputBuffer, readBuffer)))
		{
			return;
		}
		string cmdKey = GetCmdKey(readBuffer, isAck: true);
		if (readBuffer[14] == 165)
		{
			if (Enumerable.SequenceEqual(LastXinputBuffer, readBuffer))
			{
				return;
			}
			switch (readBuffer[15])
			{
			case 16:
			{
				FLog.d("CallBack-- XInputDataManager: HandleGamePadInfo");
				if (!UsbDataManager._ackCmdFlags.TryGetValue(cmdKey, out var value) || !value)
				{
					UsbDataManager._ackCmdFlags[cmdKey] = true;
					HandleGamePadInfo(readBuffer);
				}
				break;
			}
			case 17:
				HandleDongleInfo(readBuffer);
				break;
			case 32:
			{
				if (!UsbDataManager._ackCmdFlags.TryGetValue(cmdKey, out var value5) || !value5)
				{
					UsbDataManager._ackCmdFlags[cmdKey] = true;
					HandleGamepadConfigId(readBuffer);
				}
				else if (!IsActiveReadCFGID)
				{
					HandleGamepadConfigId(readBuffer);
				}
				break;
			}
			case 34:
				HandleGamepadConfigReadCB(readBuffer);
				break;
			case 39:
				HandleLedConfigReadCB(readBuffer);
				break;
			case 37:
				FLog.d("xbox data recv StartKMPC:");
				HandleStartWriteGamepadConfig();
				break;
			case 36:
				HandleWriteGamepadConfigCBK(readBuffer);
				break;
			case 42:
				FLog.d("xbox data recv StartWriteLED:");
				HandleStartWriteLEDConfig();
				break;
			case 40:
				FLog.d("xbox data recv StartFlashWriteLED:");
				HandleStartWriteLEDConfig();
				break;
			case 41:
				HandleWriteLEDConfigCBK(readBuffer);
				break;
			case 35:
				HandleStartWriteGamepadConfig();
				break;
			case 160:
				HandlerUUIDCB(readBuffer);
				break;
			case 65:
				HandlerNRFLossCount(readBuffer);
				break;
			case 48:
				switch (readBuffer[16])
				{
				case 7:
					HandleK1TriggerInfo(readBuffer);
					break;
				case 4:
				{
					UsbDataManager._ackCmdFlags.TryGetValue(cmdKey, out var value3);
					FLog.d("isFirstAckReceived3:" + value3);
					if (!UsbDataManager._ackCmdFlags.TryGetValue(cmdKey, out var value4) || !value4)
					{
						UsbDataManager._ackCmdFlags[cmdKey] = true;
						HanderScreenInfoSleepTime(readBuffer);
					}
					break;
				}
				case 2:
					HanderScreenInfo(readBuffer);
					break;
				case 16:
					ScreenDataTransService.HandlerPicData(24, 0, 0, 0);
					break;
				case 18:
					ScreenDataTransService.CloseStream(UsbDataManager.FDGDeviceInfo);
					break;
				case 17:
					ScreenDataTransService.HandlerPicData(24, 0, 0, 0);
					break;
				case 1:
				{
					string cmdKeyV = GetCmdKeyV3(readBuffer, isAck: true);
					if (!UsbDataManager._ackCmdFlags.TryGetValue(cmdKeyV, out var value2) || !value2)
					{
						HanderExtensionChipInfo(readBuffer);
					}
					break;
				}
				}
				break;
			case 96:
			{
				byte b = readBuffer[16];
				if (b != 1 && b == 2)
				{
					KeyBrustService.HandleBurstInfo(readBuffer);
				}
				break;
			}
			case 80:
				switch (readBuffer[16])
				{
				case 3:
					HandlerSaveFlashConfigCB(readBuffer);
					break;
				case 2:
					HandlerReadRandomIdCB(readBuffer);
					break;
				case 5:
					HandlerSwitchConfigIdCB(readBuffer);
					break;
				case 4:
					HandlerReadAllConfigRandomIDCB(readBuffer);
					break;
				case 7:
					HandlerAllFuncSetConfigCB(readBuffer);
					break;
				}
				break;
			}
		}
		else
		{
			try
			{
				UsbDataManager.PkgNum++;
				if (UsbDataManager.IsOpenKeyMouFunc && readBuffer[0] == 0 && readBuffer[1] == 20 && readBuffer[14] != 90)
				{
					if (GamePadVersionUtils.IsK2Serial(UsbDataManager.FDGDeviceInfo))
					{
						KeyMouDataParse.ParseXInputData(readBuffer, UsbDataManager.FDGDeviceInfo);
					}
					else
					{
						KeyMouDataParse.ParseXInputData(readBuffer, UsbDataManager.FDGDeviceInfo);
					}
				}
			}
			catch (Exception ex2)
			{
				FLog.d("KeyMouDataParse.ParseXInputData Exception:" + ex2.Message + ex2.StackTrace);
			}
		}
		LastXinputBuffer = readBuffer;
	}

	public void GetDeviceInfo()
	{
		FLog.d("GetDeviceInfo");
		byte[] cmd = XinputCommand.getSendData(CommandDic.SubCmdId["GamePadInfo"]);
		SendByteArray(cmd);
		string cmdKey = GetCmdKey(cmd);
		UsbDataManager._ackCmdFlags[cmdKey] = false;
		UsbDataManager.cts = new CancellationTokenSource();
		Task.Delay(1000 + 200 * UsbDataManager.MaxRetryGamepadInfoNum, UsbDataManager.cts.Token).ContinueWith((Task t) =>
		{
			if (!t.IsCanceled && UsbDataManager.retries < UsbDataManager.MaxRetryGamepadInfoNum)
			{
				FLog.d($"【Xinput Gamepad Info Retry：{UsbDataManager.retries}】");
				ResendDataPacket(cmd);
			}
			else
			{
				UsbDataManager.retries = 0;
			}
		});
	}

	public void GetDongleInfo()
	{
		FLog.d("Xinput - GetDongleInfo");
		byte[] sendData = XinputCommand.getSendData(CommandDic.SubCmdId["DongleInfo"]);
		SendByteArray(sendData);
		string cmdKey = GetCmdKey(sendData);
		UsbDataManager._ackCmdFlags[cmdKey] = false;
		UsbDataManager.dongle_cts = new CancellationTokenSource();
		Task.Delay(500 + 100 * UsbDataManager.MaxRetryGamepadInfoNum, UsbDataManager.dongle_cts.Token).ContinueWith((Task t) =>
		{
			FLog.d($"【XInput GetDongleInfo Retry 1：{UsbDataManager.retries}_{UsbDataManager.MaxRetryGamepadInfoNum}_{t.IsCanceled}】");
			if (!t.IsCanceled && UsbDataManager.retries < UsbDataManager.MaxRetryGamepadInfoNum)
			{
				FLog.d($"【GetDongleInfo Retry 2：{UsbDataManager.retries}】");
				UsbDataManager.retries++;
				GetDongleInfo();
			}
			else
			{
				UsbDataManager.retries = 0;
			}
		});
	}

	public bool GetScreenInfo()
	{
		SendByteArray(XinputCommand.getK1Info(2));
		return true;
	}

	public bool SwitchConfig(int ConfigId)
	{
		byte[] sendData = XinputCommand.getSendData(80, 5, (byte)ConfigId);
		SendByteArray(sendData);
		UsbDataManager.cts = new CancellationTokenSource();
		Task.Delay(2000, UsbDataManager.cts.Token).ContinueWith((Task t) =>
		{
			if (!t.IsCanceled)
			{
				FLog.d($"【SwitchConfig Retry：{UsbDataManager.retries}】");
				int num = 2;
				if (UsbDataManager.retries < num)
				{
					UsbDataManager.retries++;
					SwitchConfig(ConfigId);
				}
			}
		});
		return true;
	}

	public bool SwitchMapConfig(byte status)
	{
		byte[] sendData = XinputCommand.getSendData(80, 6, status);
		SendByteArray(sendData);
		return true;
	}

	public bool Calibration(byte status)
	{
		byte[] sendData = XinputCommand.getSendData(20, status);
		SendByteArray(sendData);
		return true;
	}

	public bool ReadAllConfigRandomId()
	{
		byte[] sendData = XinputCommand.getSendData(80, 4);
		SendByteArray(sendData);
		UsbDataManager.cts?.Cancel();
		UsbDataManager.cts = new CancellationTokenSource();
		Task.Delay(500, UsbDataManager.cts.Token).ContinueWith((Task t) =>
		{
			if (!t.IsCanceled)
			{
				FLog.d($"【SwitchConfig Retry：{UsbDataManager.retries}】");
				if (UsbDataManager.retries < UsbDataManager.MaxRetryNum)
				{
					UsbDataManager.retries++;
					ReadAllConfigRandomId();
				}
			}
		});
		return true;
	}

	public bool ApplyScreenInfo(FDGDeviceScreenInfo fdgScreenInfo)
	{
		byte[] data = XinputCommand.setK1Info(3, (byte)fdgScreenInfo.statusbarStatus);
		SendByteArray(data);
		return true;
	}

	public void ReadGamePadConfig(GamepadConfigReport gamepadConfigModel, bool isOnlyReadCfgID = false)
	{
		IsReading = true;
		IsOnlyReadCFGID = isOnlyReadCfgID;
		TempConfigListByte.Clear();
		CurrentGamepadConfig = gamepadConfigModel;
		if (!UsbDataManager.gFdgDeviceDic.ContainsKey(CurrentGamepadConfig.ReportId))
		{
			return;
		}
		try
		{
			byte[] sendData = XinputCommand.getSendData(CommandDic.SubCmdId["ReadConfigId"], (byte)gamepadConfigModel.GamepadConfigId);
			FLog.d("Start ReadConfgIdCmd:" + DataUtils.ByteToHexString(sendData));
			FLog.d("DeviceId:" + UsbDataManager.gFdgDeviceDic[gamepadConfigModel.ReportId].DeviceId);
			if (UsbDataManager.gFdgDeviceDic[gamepadConfigModel.ReportId].DeviceId >= 0)
			{
				SendByteArray(sendData);
			}
		}
		catch (Exception ex)
		{
			FLog.d("GetGamePadConfig Exception Message:" + ex.Message);
		}
	}

	public void WriteGamePadConfig(List<List<byte>> list, IDelegateCallback writeConfigCallback, bool isFlash)
	{
		FLog.d("WriteGamePadConfig count:" + list.Count + "IsWriting:" + IsWriting);
		if (list.Count > 0 && list != null && !IsWriting)
		{
			WriteConfigCallback = writeConfigCallback;
			IsWriting = true;
			IsStartSend = false;
			FullConfigList.Clear();
			FullConfigList.AddRange(list);
			FullPackageCount = FullConfigList.Count - 1;
			CurrentWPIndex = 0;
			ReadPackageId = 0;
			FLog.d("Start To Write Config Package Length:" + list.Count);
			SendFullConfigDataPacket();
		}
	}

	public void HandleGamePadInfo(byte[] readBuffer)
	{
		if (UsbDataManager.gFdgDeviceDic.Count <= 0 || !UsbDataManager.gFdgDeviceDic.ContainsKey(UsbDataManager.ReportIndex))
		{
			return;
		}
		UsbDataManager.retries = 0;
		UsbDataManager.cts?.Cancel();
		FDGDeviceInfo currentDeviceInfo = GetCurrentDeviceInfo(UsbDataManager.ReportIndex);
		if (currentDeviceInfo == null)
		{
			return;
		}
		byte deviceIdInFlash = (byte)(currentDeviceInfo.DeviceId = readBuffer[16]);
		currentDeviceInfo.DeviceIdInFlash = deviceIdInFlash;
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
			readBuffer[17],
			readBuffer[18],
			readBuffer[19],
			readBuffer[20]
		};
		byte[] deviceMac2 = new byte[4]
		{
			readBuffer[20],
			readBuffer[19],
			readBuffer[18],
			readBuffer[17]
		};
		currentDeviceInfo.DeviceMac = DataUtils.ByteToHexStringNew(deviceMac).Trim(new char[1] { ':' });
		currentDeviceInfo.DeviceMacFixed = DataUtils.ByteToHexStringNew(deviceMac2).Trim(new char[1] { ':' });
		byte b = readBuffer[21];
		byte b2 = readBuffer[22];
		int num2 = b & 0xF;
		int num3 = b >> 4;
		int num4 = b2 & 0xF;
		int num5 = b2 >> 4;
		int num6 = readBuffer[23];
		byte b3 = readBuffer[24];
		byte b4 = readBuffer[25];
		byte b5 = readBuffer[26];
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
		currentDeviceInfo.FirmwareVersionCode = num5 * 1000 + num4 * 100 + num3 * 10 + num2;
		currentDeviceInfo.FirmwareVersion = num5 + "." + num4 + "." + num3 + "." + num2;
		currentDeviceInfo.BatteryPercent = batteryPercent;
		currentDeviceInfo.MotionSensorType = ((b5 == 1) ? "QST" : "ST");
		currentDeviceInfo.SelCfgId = readBuffer[27];
		if ((b3 & 0xFF) > 0)
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
			if ((b4 & 0xFF) == 1)
			{
				currentDeviceInfo.ConnectType = FDGConncetType.wired;
				currentDeviceInfo.CpuName = "ch573";
			}
			else
			{
				currentDeviceInfo.ConnectType = FDGConncetType.wireless;
				currentDeviceInfo.CpuName = "ch571";
				GetDongleInfo();
			}
		}
		switch (currentDeviceInfo.DeviceId)
		{
		case 20:
		case 21:
		case 23:
			currentDeviceInfo.GameHadleName = "f1";
			if (currentDeviceInfo.CpuType == "wch")
			{
				currentDeviceInfo.GameHadleName = "f1wch";
			}
			break;
		case 19:
			currentDeviceInfo.GameHadleName = "apex2";
			break;
		case 22:
			currentDeviceInfo.GameHadleName = "f1p";
			break;
		case 24:
			currentDeviceInfo.GameHadleName = "k1";
			break;
		case 25:
			currentDeviceInfo.GameHadleName = "fp1";
			break;
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
		}
		UsbDataManager.MaxRetryNum = 0;
		switch (currentDeviceInfo.GameHadleName)
		{
		case "f1":
		case "f1wch":
			Constant.CURRENT_DEVICE_TYPE = 0;
			break;
		case "apex2":
			Constant.CURRENT_DEVICE_TYPE = 1;
			break;
		case "f1p":
			Constant.CURRENT_DEVICE_TYPE = 2;
			break;
		case "k1":
		case "fp1":
		case "K1Pirate":
		case "K1SF":
			Constant.CURRENT_DEVICE_TYPE = 3;
			break;
		case "f3":
		case "f3pip":
		case "f3p":
		case "f3peva":
			UsbDataManager.MaxRetryNum = 3;
			break;
		case "k2":
		case "k2hsh":
			UsbDataManager.MaxRetryNum = 5;
			break;
		default:
			UsbDataManager.MaxRetryNum = 0;
			break;
		}
		currentDeviceInfo.IsConnect = true;
		currentDeviceInfo.Keys = GamePadHelper.GetKeysByDeviceId(currentDeviceInfo.DeviceId);
		if (currentDeviceInfo.DeviceId > 0)
		{
			GamePadVersionUtils.UpdageGamepadConfigInfo(currentDeviceInfo);
			PackageLength = (byte)currentDeviceInfo.PackageLength;
			TempConfigArrByte = new byte[PackageLength + 1, 10];
			bool flag = false;
			if (GamePadVersionUtils.IsNeedGetExtChipInfo(currentDeviceInfo) && currentDeviceInfo.ExtChipInfo == null)
			{
				byte[] k1ExtInfo = XinputCommand.getK1ExtInfo();
				flag = true;
				string cmdKeyV = GetCmdKeyV3(k1ExtInfo);
				UsbDataManager._ackCmdFlags[cmdKeyV] = false;
				SendByteArray(k1ExtInfo);
			}
			if (GamePadVersionUtils.IsSupportSI(currentDeviceInfo) && currentDeviceInfo.ExtChipInfo == null && !flag)
			{
				byte[] k1ExtInfo2 = XinputCommand.getK1ExtInfo();
				string cmdKeyV2 = GetCmdKeyV3(k1ExtInfo2);
				UsbDataManager._ackCmdFlags[cmdKeyV2] = false;
				SendByteArray(k1ExtInfo2);
			}
		}
		ReadGamepadConfigId();
		if (currentDeviceInfo.ConnectType == FDGConncetType.wired && GamePadVersionUtils.IsFuncSupport(currentDeviceInfo) && currentDeviceInfo.DeviceId > 0)
		{
			GamepadInfoNotice.ReadGamepadInfoCB();
		}
		UsbDataManager.FDGDeviceInfo = currentDeviceInfo;
		FLog.d("CallBack-- XInput Mode Read gamehandle info(JSON)：" + JsonConvert.SerializeObject(UsbDataManager.gFdgDeviceDic));
		KeyCountService.InitData(UsbDataManager.FDGDeviceInfo.DeviceMac);
		KeyCountService.UpdateStartUserTime(currentDeviceInfo.DeviceMac);
	}

	public void HandleGamepadConfigId(byte[] readBuffer)
	{
		FDGDeviceInfo currentDeviceInfo = GetCurrentDeviceInfo(UsbDataManager.ReportIndex);
		if (currentDeviceInfo != null)
		{
			currentDeviceInfo.SelCfgId = readBuffer[16];
			currentDeviceInfo.SelSwitchCfgId = 4;
			if (readBuffer[17] == 160)
			{
				currentDeviceInfo.SelSwitchCfgId = readBuffer[18];
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

	public void HandleDongleInfo(byte[] readBuffer)
	{
		UsbDataManager.retries = 0;
		UsbDataManager.dongle_cts?.Cancel();
		FDGDeviceInfo currentDeviceInfo = GetCurrentDeviceInfo(UsbDataManager.ReportIndex);
		if (currentDeviceInfo != null)
		{
			byte b = readBuffer[16];
			byte b2 = readBuffer[17];
			int num = b2 & 0xF;
			int num2 = b2 >> 4;
			int num3 = b & 0xF;
			int num4 = b >> 4;
			if (num + num2 + num3 + num4 > 0)
			{
				currentDeviceInfo.DongleVersion = num4 + "." + num3 + "." + num2 + "." + num;
				FLog.d("xinput dongle Version :" + currentDeviceInfo.DongleVersion);
				currentDeviceInfo.ConnectType = FDGConncetType.wireless;
			}
			else
			{
				currentDeviceInfo.ConnectType = FDGConncetType.wired;
			}
			if (GamePadVersionUtils.IsFuncSupport(currentDeviceInfo) && currentDeviceInfo.DeviceId > 0)
			{
				GamepadInfoNotice.ReadGamepadInfoCB();
			}
		}
	}

	public void HanderScreenInfoSleepTime(byte[] readBuffer)
	{
		FDGDeviceInfo currentDeviceInfo = GetCurrentDeviceInfo(UsbDataManager.ReportIndex);
		if (currentDeviceInfo != null)
		{
			if (currentDeviceInfo.ScreenInfo == null)
			{
				currentDeviceInfo.ScreenInfo = new FDGDeviceScreenInfo();
			}
			currentDeviceInfo.ScreenInfo.sleepTime = readBuffer[17];
			currentDeviceInfo.ScreenInfo.isSwitch = readBuffer[18] == 1;
			if (readBuffer[17] == byte.MaxValue)
			{
				currentDeviceInfo.ScreenInfo.sleepTime = 15;
			}
			GamepadInfoNotice.GetSleepTimeCB(JsonConvert.SerializeObject(currentDeviceInfo));
		}
	}

	public void HanderScreenInfo(byte[] readBuffer)
	{
		FLog.d("HanderScreenInfo:" + UsbDataManager.ReportIndex);
		FDGDeviceInfo currentDeviceInfo = GetCurrentDeviceInfo(UsbDataManager.ReportIndex);
		if (currentDeviceInfo != null)
		{
			if (currentDeviceInfo.ScreenInfo == null)
			{
				currentDeviceInfo.ScreenInfo = new FDGDeviceScreenInfo();
			}
			currentDeviceInfo.ScreenInfo.statusbarStatus = readBuffer[17];
			currentDeviceInfo.ScreenInfo.resourceStatus = readBuffer[18];
			ScreenInfoReport screenInfoReport = new ScreenInfoReport();
			screenInfoReport.ReportId = UsbDataManager.ReportIndex;
			screenInfoReport.ScreenInfo = currentDeviceInfo.ScreenInfo;
			FLog.d("screenInfoR:" + JsonConvert.SerializeObject(screenInfoReport));
			FDGProtocolService.PostMessage(13, JsonConvert.SerializeObject(screenInfoReport));
		}
	}

	public void HanderExtensionChipInfo(byte[] data)
	{
		FDGDeviceInfo currentDeviceInfo = GetCurrentDeviceInfo(UsbDataManager.ReportIndex);
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
				num2 = data[17] & 0xF0;
				num = data[17] & 0xF;
				num3 = data[18] & 0xF;
				num4 = data[18] >> 4;
				num5 = data[19] & 0xF0;
				num6 = data[19] & 0xF;
				num7 = data[20] & 0xF;
				num8 = data[20] >> 4;
				num9 = data[21] & 0xF0;
				num10 = data[21] & 0xF;
				num11 = data[22] & 0xF;
				num12 = data[22] >> 4;
				extChipInfo.ExtCpuVerion = num2 + "." + num + "." + num4 + "." + num3;
				extChipInfo.LcdVersion = num5 + "." + num6 + "." + num8 + "." + num7;
				extChipInfo.SwitchExtCpuVersion = num9 + "." + num10 + "." + num12 + "." + num11;
			}
			else
			{
				num = data[17];
				num3 = data[18] & 0xF;
				num4 = data[18] >> 4;
				num6 = data[19];
				num7 = data[20] & 0xF;
				num8 = data[20] >> 4;
				num9 = data[21] & 0xF;
				num10 = data[21] >> 4;
				num11 = data[22] & 0xF;
				num12 = data[22] >> 4;
				extChipInfo.ExtCpuVerion = num + "." + num4 + "." + num3;
				extChipInfo.LcdVersion = num6 + "." + num8 + "." + num7;
				extChipInfo.SwitchExtCpuVersion = num10 + "." + num9 + "." + num12 + "." + num11;
			}
			byte b = data[23];
			_ = data[24];
			byte b2 = data[25];
			byte b3 = data[26];
			int versionNumber = (b << 8) | b;
			extChipInfo.PYVersion = DataUtils.FormateVersion(versionNumber);
			versionNumber = (b2 << 8) | b3;
			extChipInfo.Bs21Version = DataUtils.FormateVersion(versionNumber);
			currentDeviceInfo.ExtChipInfo = extChipInfo;
			GamepadInfoNotice.NotifyGamepadInfoUpdate();
		}
	}

	public async void HandleGamepadConfigReadCB(byte[] readBuffer)
	{
		int num = readBuffer[16];
		if (!IsReading)
		{
			return;
		}
		if (num <= PackageLength)
		{
			UpdateTempArrayByte(readBuffer);
		}
		FLog.d(string.Format("【XInput】Read Cfg ID:{0}- CallBack Length::{1} Index:{2} Receive Length:{3} ", new object[4] { CurrentGamepadConfig.GamepadConfigId, PackageLength, num, TempConfigArrByte.Length }));
		if (num != PackageLength)
		{
			return;
		}
		IsReading = false;
		if (CurrentGamepadConfig != null)
		{
			GamepadConfigBase.CurrentDeviceId = UsbDataManager.gFdgDeviceDic[UsbDataManager.ReportIndex].DeviceId;
			List<byte> list = new List<byte>();
			for (int i = 0; i < TempConfigArrByte.GetLength(0); i++)
			{
				for (int j = 0; j < TempConfigArrByte.GetLength(1); j++)
				{
					list.Add(TempConfigArrByte[i, j]);
				}
			}
			if (list.Count >= 2)
			{
				UsbDataManager.CurrentConfigVersion = BitConverter.ToInt16(new byte[2]
				{
					list[1],
					list[0]
				}, 0);
			}
			FLog.d($"【XInput】CurrentConfigVersion:{list[1]}");
			if (list[1] == 1)
			{
				CurrentGamepadConfig.ConfigBean = GamepadConfigUtilsV1.ConvertGPConfigByByte(list);
			}
			else if (list[1] == 2)
			{
				CurrentGamepadConfig.ConfigBean = GamepadConfigUtilsV2.ConvertGPConfigByByte(list);
			}
			else if (list[1] == 3)
			{
				CurrentGamepadConfig.ConfigBean = GamepadConfigUtilsV3.ConvertGPConfigByByte(list);
			}
			if (CurrentGamepadConfig.ConfigBean != null)
			{
				FDGDeviceInfo fDGDeviceInfo = UsbDataManager.gFdgDeviceDic[UsbDataManager.ReportIndex];
				FLog.d("currentDeviceInfo:" + JsonConvert.SerializeObject(fDGDeviceInfo));
				bool flag = GamePadVersionUtils.IsSupportNewLedConfig(fDGDeviceInfo);
				FLog.d("isSupportNewLedConfig:" + flag);
				if (flag)
				{
					await Task.Delay(50).ContinueWith((Task t) =>
					{
						ReadNewLedConfig(CurrentGamepadConfig);
					});
				}
				else
				{
					FLog.d("IsOnlyReadCFGID:" + IsOnlyReadCFGID);
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
		FLog.d("Gamepad Config Info is read Finished");
	}

	public void HandleStartWriteGamepadConfig()
	{
		FLog.d("IsStartSend:" + IsStartSend);
		FLog.d("IsStartSend:" + IsStartSend);
		UsbDataManager.retries = 0;
		UsbDataManager.cts?.Cancel();
		if (!IsStartSend)
		{
			CurrentWPIndex++;
			SendFullConfigDataPacket();
			IsStartSend = true;
		}
	}

	public void HandleWriteGamepadConfigCBK(byte[] readBuffer)
	{
		FLog.d($"Gamepad Config CB【ReadPackageId:{ReadPackageId}】 【FullPackageCount:{FullPackageCount}】【CurrentWPIndex:{CurrentWPIndex}】");
		if (WriteConfigCallback == null)
		{
			return;
		}
		UsbDataManager.retries = 0;
		UsbDataManager.cts?.Cancel();
		if (IsWriteFlash)
		{
			ReadPackageId++;
		}
		else
		{
			ReadPackageId = readBuffer[16];
		}
		if (ReadPackageId < CurrentWPIndex)
		{
			return;
		}
		CurrentWPIndex++;
		if (CurrentWPIndex > FullPackageCount || ReadPackageId == FullPackageCount)
		{
			if (IsWriting)
			{
				FLog.d($"Gamepad Config Send Success【ReadPackageId:{ReadPackageId}】 【FullPackageCount:{FullPackageCount}】【CurrentWPIndex:{CurrentWPIndex}】");
				FullConfigList.Clear();
				CurrentWPIndex = 0;
				IsWriting = false;
				if (ReadPackageId == FullPackageCount)
				{
					WriteConfigCallback(100);
					IsStartSend = false;
				}
				FLog.d($"Gamepad Config Send Success【IsWriting:{IsWriting}】");
			}
		}
		else
		{
			SendFullConfigDataPacket();
		}
	}

	public void HandleK1TriggerInfo(byte[] readBuffer)
	{
	}

	public bool SendByteArray(byte[] data)
	{
		if (!XBoxFilter.canWrite())
		{
			FLog.d("XFilter: CanWrite:------------>>： " + XBoxFilter.canWrite());
			return false;
		}
		try
		{
			IntPtr intPtr = Marshal.AllocHGlobal(data.Length);
			Marshal.Copy(data, 0, intPtr, data.Length);
			bool flag = XBoxFilter.writeData(intPtr, (uint)data.Length);
			FLog.d($"XFilter WriteData[{data.Length}]: {DataUtils.ByteToHexString(data)}:------------>>:{flag}");
			return flag;
		}
		catch (Exception ex)
		{
			FLog.d("Xinput Mode Write Error:" + ex.Message);
		}
		return false;
	}

	public static XInputDataManager GetCurrentInstance()
	{
		if (currentInstance == null)
		{
			currentInstance = new XInputDataManager();
		}
		return currentInstance;
	}

	public bool CallbackDataReceive(IntPtr pData, uint Context)
	{
		try
		{
			if (pData == IntPtr.Zero)
			{
				FLog.d("xboxfilter callback error");
			}
			PXBOX_DATA_ITEM pXBOX_DATA_ITEM = (PXBOX_DATA_ITEM)Marshal.PtrToStructure(pData, typeof(PXBOX_DATA_ITEM));
			if (pXBOX_DATA_ITEM.usbData == null)
			{
				return false;
			}
			DataUtils.ByteToHexString(pXBOX_DATA_ITEM.usbData);
			if (pXBOX_DATA_ITEM.usbData.Length >= 32)
			{
				_ = pXBOX_DATA_ITEM.usbData[1];
				_ = 20;
				ResolveUsbData(pXBOX_DATA_ITEM.usbData);
			}
		}
		catch (Exception ex)
		{
			FLog.d("XInputDataManager callback error" + ex.Message + "Exception:" + ex.StackTrace);
		}
		return true;
	}

	private void ResendDataPacket(byte[] Cmd)
	{
		FLog.d(string.Format("【ResendDataPacket retries:】:{0}__MaxRetryGamepadInfoNum:{1}___currentIndex:{2}___CurrentWPIndex:{3}", new object[4]
		{
			UsbDataManager.retries,
			UsbDataManager.MaxRetryGamepadInfoNum,
			currentIndex,
			CurrentWPIndex
		}));
		if (UsbDataManager.retries < UsbDataManager.MaxRetryGamepadInfoNum && currentIndex == CurrentWPIndex)
		{
			UsbDataManager.retries++;
			GetDeviceInfo();
		}
	}

	public bool GetSleepTimeInfo()
	{
		if (!GamePadVersionUtils.IsFPSerial(UsbDataManager.FDGDeviceInfo))
		{
			GamePadVersionUtils.IsM1(UsbDataManager.FDGDeviceInfo);
		}
		byte[] k1Info = XinputCommand.getK1Info(4);
		SendByteArray(k1Info);
		string cmdKey = GetCmdKey(k1Info);
		UsbDataManager._ackCmdFlags[cmdKey] = false;
		return true;
	}

	public bool GetAllFuncSetConfigStatus()
	{
		byte[] gamePadMapConfigCmd = XinputCommand.GetGamePadMapConfigCmd(7);
		SendByteArray(gamePadMapConfigCmd);
		string cmdKey = GetCmdKey(gamePadMapConfigCmd);
		UsbDataManager._ackCmdFlags[cmdKey] = false;
		return true;
	}

	public bool SwitchXInput2Android()
	{
		byte[] sendData = XinputCommand.getSendData(23);
		return SendByteArray(sendData);
	}

	public bool SwitchXInput2OTA()
	{
		byte[] sendData = XinputCommand.getSendData(48, 15);
		return SendByteArray(sendData);
	}

	public void ReadNewLedConfig(GamepadConfigReport gamepadConfigModel)
	{
		FLog.d("Start Read Led ConfgId ReadNewLedConfig 00");
		IsLEDReading = true;
		TempLedConfigListByte.Clear();
		CurrentGamepadConfig = gamepadConfigModel;
		if (!UsbDataManager.gFdgDeviceDic.ContainsKey(CurrentGamepadConfig.ReportId))
		{
			return;
		}
		try
		{
			byte[] sendData = XinputCommand.getSendData(CommandDic.SubCmdId["ReadLedConfigById"], (byte)gamepadConfigModel.GamepadConfigId);
			FLog.d("Start Read Led ConfgId Cmd  11:" + DataUtils.ByteToHexString(sendData));
			if (UsbDataManager.gFdgDeviceDic[gamepadConfigModel.ReportId].DeviceId >= 0)
			{
				FLog.d("Start Read Led ConfgId 22:");
				SendByteArray(sendData);
			}
		}
		catch (Exception ex)
		{
			FLog.d("Get GamePad Led Config Exception Message:" + ex.Message);
		}
	}

	public void ReadGamepadConfigId()
	{
		IsActiveReadCFGID = true;
		byte[] sendData = XinputCommand.getSendData(CommandDic.SubCmdId["GetCurConfigId"]);
		SendByteArray(sendData);
		string cmdKey = GetCmdKey(sendData);
		UsbDataManager._ackCmdFlags[cmdKey] = false;
	}

	public void UpdateGamePadInfo()
	{
	}

	public FDGDeviceExtChipInfo GetExtChipInfo()
	{
		if (mFDGExtChipInfo == null)
		{
			mFDGExtChipInfo = new FDGDeviceExtChipInfo();
		}
		return mFDGExtChipInfo;
	}

	public void HandleLedConfigReadCB(byte[] readBuffer)
	{
		int num = readBuffer[16];
		if (!IsLEDReading)
		{
			return;
		}
		if (num <= LedPackageLength)
		{
			UpdateTempLedConfigArrayByte(readBuffer);
		}
		FLog.d(string.Format("【XInput】Read LED Cfg ID:{0}- CallBack Length::{1} Index:{2} Receive Length:{3} ", new object[4] { CurrentGamepadConfig.GamepadConfigId, LedPackageLength, num, TempLedConfigArrayByte.Length }));
		if (num != LedPackageLength)
		{
			return;
		}
		IsLEDReading = false;
		if (CurrentGamepadConfig != null)
		{
			GamepadConfigBase.CurrentDeviceId = UsbDataManager.gFdgDeviceDic[UsbDataManager.ReportIndex].DeviceId;
			List<byte> list = new List<byte>();
			for (int i = 0; i < TempLedConfigArrayByte.GetLength(0); i++)
			{
				for (int j = 0; j < TempLedConfigArrayByte.GetLength(1); j++)
				{
					list.Add(TempLedConfigArrayByte[i, j]);
				}
			}
			CurrentGamepadConfig.ConfigBean.Basic.NewLedConfig = GamepadConfigUtilsV2.ConvertLEDConfigByByte(list);
			if (CurrentGamepadConfig.ConfigBean != null && GamePadVersionUtils.IsSupportNewLedConfig(UsbDataManager.gFdgDeviceDic[UsbDataManager.ReportIndex]))
			{
				GamepadConfigNotice.ReadConfigCB(CurrentGamepadConfig);
				TempLedConfigListByte.Clear();
			}
		}
		FLog.d("LED Config Info is read Finished");
	}

	public void HandleStartWriteLEDConfig()
	{
		FLog.d("IsStartSend:" + IsStartSend);
		UsbDataManager.retries = 0;
		UsbDataManager.cts?.Cancel();
		if (!IsStartSend)
		{
			CurrentWPIndex++;
			SendFullConfigDataPacket();
			IsStartSend = true;
		}
	}

	public void HandleWriteLEDConfigCBK(byte[] readBuffer)
	{
		FLog.d($"Gamepad LED Config CB【ReadPackageId:{ReadPackageId}】 【FullPackageCount:{FullPackageCount}】【CurrentWPIndex:{CurrentWPIndex}】");
		if (WriteConfigCallback == null)
		{
			return;
		}
		UsbDataManager.retries = 0;
		UsbDataManager.cts?.Cancel();
		if (IsWriteFlash)
		{
			ReadPackageId++;
		}
		else
		{
			ReadPackageId = readBuffer[16];
		}
		if (ReadPackageId < CurrentWPIndex)
		{
			return;
		}
		CurrentWPIndex++;
		if (CurrentWPIndex > FullPackageCount || ReadPackageId == FullPackageCount)
		{
			if (IsWriting)
			{
				FLog.d($"Gamepad LED Config Send Success【ReadPackageId:{ReadPackageId}】 【FullPackageCount:{FullPackageCount}】【CurrentWPIndex:{CurrentWPIndex}】");
				FullConfigList.Clear();
				CurrentWPIndex = 0;
				if (ReadPackageId == FullPackageCount)
				{
					WriteConfigCallback(100);
					IsStartSend = false;
				}
				IsWriting = false;
			}
		}
		else
		{
			SendFullConfigDataPacket();
		}
	}

	private void SendFullConfigDataPacket(bool IsReSend = false, int retray = 1)
	{
		FLog.d($"CurrentWPIndex:{CurrentWPIndex}_FullConfigList.Count:{FullConfigList.Count}");
		bool flag = false;
		if (!((!IsReSend) ? (CurrentWPIndex < FullConfigList.Count) : (CurrentWPIndex <= FullConfigList.Count)))
		{
			return;
		}
		currentIndex = CurrentWPIndex;
		FLog.d($"Gamepad Config Send Config Daata:【ReadPackageId:{ReadPackageId}】 【FullPackageCount:{FullPackageCount}】【CurrentWPIndex:{CurrentWPIndex}】");
		byte[] array = FullConfigList[CurrentWPIndex].ToArray();
		if (IsReSend)
		{
			array[^1] = (byte)(array[^1] + retray);
		}
		SendByteArray(array);
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
		FLog.d(string.Format("重传1【ResendDataPacket】:retry:{0}___Max:{1}__currentIndex:{2}___CurrentWPIndex:{3}", new object[4]
		{
			UsbDataManager.retries,
			UsbDataManager.MaxRetryNum,
			currentIndex,
			CurrentWPIndex
		}));
		if (UsbDataManager.retries < UsbDataManager.MaxRetryNum && currentIndex == CurrentWPIndex)
		{
			UsbDataManager.retries++;
			SendFullConfigDataPacket(IsReSend: true, UsbDataManager.retries);
			FLog.d($"重传2【ResendDataPacket】:{UsbDataManager.retries}__currentIndex:{currentIndex}___CurrentWPIndex:{CurrentWPIndex}");
		}
	}

	public void UpdateTempListByte(byte[] readBuffer)
	{
		try
		{
			int num = 10;
			int num2 = 17;
			if (readBuffer.Length != 0 && readBuffer.Length <= 32 && readBuffer.Length == 32)
			{
				_ = readBuffer[16];
				for (int i = 0; i < num; i++)
				{
					TempConfigListByte.Add(readBuffer[i + num2]);
				}
			}
		}
		catch (Exception ex)
		{
			FLog.d("Update Temp Config List Exception Msg:" + ex.Message);
		}
	}

	public void UpdateTempArrayByte(byte[] readBuffer)
	{
		int num = 10;
		int num2 = 17;
		try
		{
			if (readBuffer.Length == 0 || readBuffer.Length > 32 || readBuffer.Length != 32)
			{
				return;
			}
			byte b = readBuffer[16];
			if (b == 0)
			{
				if (readBuffer[num2] == 1 && readBuffer[num2 + 1] == 3)
				{
					PackageLength = Constant.PackLengthNewV31;
				}
				TempConfigArrByte = new byte[PackageLength + 1, 10];
			}
			for (int i = 0; i < num; i++)
			{
				TempConfigArrByte[b, i] = readBuffer[i + num2];
			}
		}
		catch (Exception ex)
		{
			FLog.d("Update Temp Config Array Exception Msg:" + ex.Message);
		}
	}

	public void UpdateTempLedConfigListByte(byte[] readBuffer)
	{
		try
		{
			int num = 10;
			int num2 = 17;
			if (readBuffer.Length != 0 && readBuffer.Length <= 32 && readBuffer.Length == 32)
			{
				_ = readBuffer[16];
				for (int i = 0; i < num; i++)
				{
					TempLedConfigListByte.Add(readBuffer[i + num2]);
				}
			}
		}
		catch (Exception ex)
		{
			FLog.d("Update Temp Config List Exception Msg:" + ex.Message);
		}
	}

	public void UpdateTempLedConfigArrayByte(byte[] readBuffer)
	{
		try
		{
			int num = 10;
			int num2 = 17;
			if (readBuffer.Length != 0 && readBuffer.Length <= 32 && readBuffer.Length == 32)
			{
				byte b = readBuffer[16];
				for (int i = 0; i < num; i++)
				{
					TempLedConfigArrayByte[b, i] = readBuffer[i + num2];
				}
			}
		}
		catch (Exception ex)
		{
			FLog.d("Update Temp Config Array Exception Msg:" + ex.Message);
		}
	}

	public static async void WriteFlash(List<List<byte>> sendFlashByteList)
	{
		if (GetCurrentInstance().IsWriting)
		{
			return;
		}
		IsWriteFlash = true;
		IsWriteFlashSuccess = false;
		GetCurrentInstance().WriteGamePadConfig(sendFlashByteList, (int result) =>
		{
			if (result == 100)
			{
				FLog.d("WriteFlash:" + result);
				IsWriteFlash = false;
				IsWriteFlashSuccess = true;
			}
		}, isFlash: true);
	}

	public static async void WriteLEDFlash(List<List<byte>> sendFlashByteList)
	{
		if (GetCurrentInstance().IsWriting)
		{
			return;
		}
		IsWriteFlash = true;
		IsWriteFlashLedSuccess = false;
		GetCurrentInstance().WriteGamePadConfig(sendFlashByteList, (int result) =>
		{
			if (result == 100)
			{
				FLog.d("WriteFlash:" + result);
				IsWriteFlash = false;
				IsWriteFlashLedSuccess = true;
			}
		}, isFlash: true);
	}

	public static async void BuildDataAndWrite(FDGDeviceInfo fdgDeviceInfo, GamepadConfigReport gamepadConfigModel)
	{
		IsSuccessNotify = false;
		ConfigApplier configApplier = new ConfigApplier();
		ConfigApplier.SetIsApplySuccessed(IsSuccessNotify);
		ConfigApplier._cts?.Cancel();
		if (GetCurrentInstance().IsWriting || (gamepadConfigModel == null && gamepadConfigModel.ConfigBean == null))
		{
			return;
		}
		FLog.d("XInputBuildDataWrite fdgDeviceInfo:" + JsonConvert.SerializeObject(fdgDeviceInfo));
		FLog.d("XInputBuildDataWrite gamepadConfigModel:" + JsonConvert.SerializeObject(gamepadConfigModel));
		FLog.d("Config Version1:" + JsonConvert.SerializeObject(fdgDeviceInfo));
		bool IsApplySuccessed = false;
		List<byte> list = null;
		List<List<byte>> sendWriteFullData = null;
		List<byte> list2 = new List<byte>();
		List<List<byte>> ExtSendWriteFullData = new List<List<byte>>();
		new List<byte>();
		List<List<byte>> NewLedSendWriteFullData = new List<List<byte>>();
		FLog.d("Config Version 2:" + fdgDeviceInfo?.ConfigVersion);
		try
		{
			FLog.d("Config Version 3:" + fdgDeviceInfo?.ConfigVersion);
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
			FLog.d("configDataList:" + list.Count);
			FLog.d("gamepadConfigModel GamepadConfigId:" + gamepadConfigModel.GamepadConfigId);
			sendWriteFullData = XInputDataUtils.FormatterWriteFullData(list, (byte)gamepadConfigModel.GamepadConfigId);
			FLog.d("sendWriteFullData length:" + sendWriteFullData.Count);
			if (GamePadVersionUtils.IsSupportAutoTrigger(fdgDeviceInfo.DeviceId) && GamePadVersionUtils.IsSupportTriggerVibration(fdgDeviceInfo) && fdgDeviceInfo.ConfigVersion == 1)
			{
				list2 = GamepadConfigUtilsV1.GetExtFullConfigListByConfig(gamepadConfigModel.ConfigBean);
				if (list2.Count > 0)
				{
					ExtSendWriteFullData = XInputDataUtils.FormatterWriteTestPartlyAppointData(list2, 4, isPermanentlySaved: true);
				}
			}
			if (GamePadVersionUtils.IsSupportNewLedConfig(fdgDeviceInfo))
			{
				List<byte> list3 = GamepadConfigUtilsV2.ConvertByteByLedConfig(gamepadConfigModel.ConfigBean);
				if (list3.Count > 0)
				{
					NewLedSendWriteFullData = XInputDataUtils.LedFormatterWriteFullData(list3, (byte)gamepadConfigModel.GamepadConfigId);
				}
			}
		}
		catch (Exception ex)
		{
			FLog.d("XInputBuildDataWrite Exception:" + ex.Message + " stack trace:" + ex.StackTrace);
		}
		for (int i = 0; i < sendWriteFullData.Count; i++)
		{
			FLog.d("X配置列表页-配置写入待发送配置:" + DataUtils.ByteToHexString(sendWriteFullData[i].ToArray()));
		}
		for (int j = 0; j < ExtSendWriteFullData.Count; j++)
		{
			FLog.d("X配置列表页-配置写入待发送配置 扩展配置:" + DataUtils.ByteToHexString(ExtSendWriteFullData[j].ToArray()));
		}
		for (int k = 0; k < NewLedSendWriteFullData.Count; k++)
		{
			FLog.d("X配置列表页-配置写入待发送配置 灯光配置:" + DataUtils.ByteToHexString(NewLedSendWriteFullData[k].ToArray()));
		}
		CancellationTokenSource _cts = new CancellationTokenSource();
		if (list2.Count > 0)
		{
			configApplier.writeConfigTask = Task.Run(() =>
			{
				FLog.d("Xinput start send data ,package length:" + sendWriteFullData.Count);
				GetCurrentInstance().WriteGamePadConfig(sendWriteFullData, (int result) =>
				{
					if (result == 100)
					{
						FLog.d("Xinput start send EXT data ,package length:" + ExtSendWriteFullData.Count);
						GetCurrentInstance().WriteGamePadConfig(ExtSendWriteFullData, (int extResult) =>
						{
							if (extResult == 100)
							{
								IsApplySuccessed = true;
								byte[] openKeyMapCmd = XinputCommand.getOpenKeyMapCmd();
								byte[] sendData = XinputCommand.getSendData(CommandDic.SubCmdId["CloseMacro"]);
								GetCurrentInstance().SendByteArray(openKeyMapCmd);
								GetCurrentInstance().SendByteArray(sendData);
								FLog.d("ApplyConfigResultCB:::: Config Without LED");
								if (!IsSuccessNotify)
								{
									IsSuccessNotify = true;
									ConfigApplier.SetIsApplySuccessed(IsSuccessNotify);
									GamepadConfigNotice.ApplyConfigResultCB(IsApplySuccessed);
									FLog.d("【gamepadConfigModel CB】  CFGID:" + gamepadConfigModel.GamepadConfigId);
								}
							}
						}, isFlash: false);
					}
				}, isFlash: false);
			}, _cts.Token);
		}
		else
		{
			configApplier.writeConfigTask = Task.Run(() =>
			{
				FLog.d("Xinput start send CONFIG data ,package length 1:" + sendWriteFullData.Count);
				GetCurrentInstance().WriteGamePadConfig(sendWriteFullData, async (int result) =>
				{
					FLog.d($"Result:{result}_ConfigApplier.IsSuccessNotify:" + ConfigApplier.IsSuccessNotify);
					if (result == 100)
					{
						if (NewLedSendWriteFullData.Count > 0)
						{
							configApplier.writeConfigTask = Task.Run(async () =>
							{
								if (ConfigApplier.IsSuccessNotify)
								{
									FLog.d("ConfigApplier.IsSuccessNotify:" + ConfigApplier.IsSuccessNotify);
								}
								else
								{
									await Task.Delay(500);
									FLog.d("Xinput start send LED data ,package length 2:" + NewLedSendWriteFullData.Count);
									GetCurrentInstance().WriteGamePadConfig(NewLedSendWriteFullData, (int num) =>
									{
										if (num == 100)
										{
											IsApplySuccessed = true;
											byte[] openKeyMapCmd2 = XinputCommand.getOpenKeyMapCmd();
											byte[] sendData2 = XinputCommand.getSendData(CommandDic.SubCmdId["CloseMacro"]);
											GetCurrentInstance().SendByteArray(openKeyMapCmd2);
											GetCurrentInstance().SendByteArray(sendData2);
											FLog.d("ApplyConfigResultCB::::Config+LED");
											if (!IsSuccessNotify)
											{
												IsSuccessNotify = true;
												ConfigApplier.SetIsApplySuccessed(IsSuccessNotify);
												GamepadConfigNotice.ApplyConfigResultCB(IsApplySuccessed);
												FLog.d("【gamepadConfigModel CB】  CFGID:" + gamepadConfigModel.GamepadConfigId);
											}
										}
									}, isFlash: false);
								}
							}, _cts.Token);
						}
						else
						{
							IsApplySuccessed = true;
							byte[] openKeyMapCmd = XinputCommand.getOpenKeyMapCmd();
							byte[] sendData = XinputCommand.getSendData(CommandDic.SubCmdId["CloseMacro"]);
							GetCurrentInstance().SendByteArray(openKeyMapCmd);
							GetCurrentInstance().SendByteArray(sendData);
							FLog.d("ApplyConfigResultCB::::Config");
							if (!IsSuccessNotify)
							{
								IsSuccessNotify = true;
								ConfigApplier.SetIsApplySuccessed(IsSuccessNotify);
								GamepadConfigNotice.ApplyConfigResultCB(IsApplySuccessed);
								FLog.d("【gamepadConfigModel CB】  CFGID:" + gamepadConfigModel.GamepadConfigId);
							}
						}
					}
				}, isFlash: false);
			}, _cts.Token);
		}
		await configApplier.ApplyConfigAsync();
		_cts?.Cancel();
	}

	public void HandlerUUIDCB(byte[] readBuffer)
	{
		GamepadUUIDReport gamepadUUIDReport = new GamepadUUIDReport();
		int num = 15;
		if (readBuffer.Count() >= 32)
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

	public void HandlerNRFLossCount(byte[] readBuffer)
	{
		GamePadCountReport gamePadCountReport = new GamePadCountReport();
		int num = 15;
		if (readBuffer.Count() >= 32)
		{
			GamepadCount gamepadCount = new GamepadCount();
			bool flag = false;
			if (UsbDataManager.FDGDeviceInfo != null && GamePadVersionUtils.IsF3Serial(UsbDataManager.FDGDeviceInfo) && string.Compare(UsbDataManager.FDGDeviceInfo.FirmwareVersion, "6.7.4.6", StringComparison.Ordinal) >= 0 && string.Compare(UsbDataManager.FDGDeviceInfo.DongleVersion, "0.4.1.6", StringComparison.Ordinal) >= 0)
			{
				flag = true;
			}
			if (readBuffer[29] == 2)
			{
				flag = true;
			}
			else if (readBuffer[29] == 1)
			{
				flag = false;
			}
			gamepadCount.DataVersionNew = flag;
			if (flag)
			{
				gamepadCount.PkgIndex = readBuffer[num + 1];
				gamepadCount.PkgLoss = (readBuffer[num + 3] << 8) | readBuffer[num + 2];
				gamepadCount.Frq1Loss = readBuffer[num + 4];
				gamepadCount.Frq2Loss = readBuffer[num + 5];
				gamepadCount.Frq3Loss = readBuffer[num + 6];
				gamepadCount.Frq4Loss = readBuffer[num + 7];
				gamepadCount.Frq5Loss = readBuffer[num + 8];
				gamepadCount.Frq6Loss = readBuffer[num + 9];
				gamepadCount.Frq7Loss = readBuffer[num + 10];
				gamepadCount.Frq8Loss = readBuffer[num + 11];
				gamepadCount.Frq9Loss = readBuffer[num + 12];
				gamepadCount.Frq10Loss = readBuffer[num + 13];
			}
			else
			{
				gamepadCount.PkgIndex = readBuffer[num + 1];
				gamepadCount.PkgLoss = (readBuffer[num + 3] << 8) | readBuffer[num + 2];
				gamepadCount.Frq1Loss = (readBuffer[num + 5] << 8) | readBuffer[num + 4];
				gamepadCount.Frq2Loss = (readBuffer[num + 7] << 8) | readBuffer[num + 6];
				gamepadCount.Frq3Loss = (readBuffer[num + 9] << 8) | readBuffer[num + 8];
				gamepadCount.Frq4Loss = (readBuffer[num + 11] << 8) | readBuffer[num + 10];
				gamepadCount.Frq5Loss = (readBuffer[num + 13] << 8) | readBuffer[num + 12];
			}
			gamePadCountReport.gamepadCount = gamepadCount;
			if (gamepadCount.PkgLoss <= 1000)
			{
				GamepadNRFLossCountService.NRFLossCountCB(JsonConvert.SerializeObject(gamePadCountReport));
			}
		}
	}
}
