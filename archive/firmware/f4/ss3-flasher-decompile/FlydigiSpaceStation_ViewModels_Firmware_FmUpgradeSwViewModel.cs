using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Threading.Tasks;
using System.Timers;
using System.Windows;
using FlydigiSpaceStation.Assets.Localization.Language;
using FlydigiSpaceStation.Common;
using FlydigiSpaceStation.Common.DataManager;
using FlydigiSpaceStation.Common.Lib;
using FlydigiSpaceStation.Common.Services.Api;
using FlydigiSpaceStation.Common.Services.Protocol;
using FlydigiSpaceStation.Common.Utils;
using LibCommon.Model;
using LibCommon.Utils;
using Microsoft.Win32.SafeHandles;
using Prism.Commands;
using Prism.Mvvm;
using Prism.Services.Dialogs;

namespace FlydigiSpaceStation.ViewModels.Firmware;

public class FmUpgradeSwViewModel : BindableBase, IDialogAware, IConfigureService
{
	[Flags]
	private enum SENDTYPE
	{
		FEATURE = 1,
		OUTPUT = 2,
		WRITE = 4
	}

	public string FirmwareName;

	public string CpuType;

	public static bool IsFoundDevice = false;

	public bool IsUpgradeSuccess;

	public FirmwareApiModel GamepadForceUpgradeModel;

	public bool IsHSH;

	private string _productName;

	private string _mainPic;

	private string startBackground;

	private string statusForeground;

	private bool isShowUpgrade;

	private bool isShowProcess;

	private bool isShowSuccess;

	private bool isShowError;

	private FirmwareApiModel firmwareModel;

	private FDGDeviceInfo currentFDGDeviceInfo;

	private DelegateCommand _CloseCommand;

	private DelegateCommand _RetryCommand;

	public object lockobj = new object();

	private DelegateCommand<string> _UpdateCommand;

	private byte[] source_binchar = new byte[2097152];

	private uint source_bin_size = 0u;

	private uint bin_crc = 0u;

	private uint bin_fw_version;

	private ushort ota_index = 0;

	private byte start_ota_flag = 0;

	private const int MAX_REPORT_DATA_NUM = 64;

	private byte[] sendBytes = new byte[64];

	private List<byte> sendLists;

	private static byte[] DefaultSendBytes = new byte[64];

	private DateTime otaStartTime;

	private long ota_jindu;

	private byte report_id = 5;

	private int InputReportByteLength = 65535;

	private int OutputReportByteLength = 65535;

	private int FeatureReportByteLength = 65535;

	private bool findDev_flag = false;

	private byte[] sendReportDataBuf = new byte[64];

	private byte[] getReportDataBuf = new byte[64];

	private int hWriteDevHandle;

	private int hReadDevHandle;

	private FileStream hidDevice = null;

	private bool get_fw_version = false;

	public Timer checkTimer;

	private string binFullPath;

	private int progressBar;

	private string status;

	private string statusStyle;

	private string uspage;

	private bool _IsLoading;

	private byte[] readFileDataBuf = new byte[64];

	private bool isShowSuccessInfo;

	private bool isShowFailedInfo;

	private string successInfo;

	private string failedInfo;

	private string _TipInfo;

	private bool _IsShowTipInfo;

	private bool _IsHideCLoseButton;

	private string _LoadingTipInfo;

	private string _UpgradeButtonText;

	public string Title
	{
		get
		{
			throw new NotImplementedException();
		}
	}

	public string ProductName
	{
		get
		{
			return _productName;
		}
		set
		{
			if (!string.Equals(_productName, value, StringComparison.Ordinal))
			{
				_productName = value;
				RaisePropertyChanged("ProductName");
			}
		}
	}

	public string MainPic
	{
		get
		{
			return _mainPic;
		}
		set
		{
			if (!string.Equals(_mainPic, value, StringComparison.Ordinal))
			{
				_mainPic = value;
				RaisePropertyChanged("MainPic");
			}
		}
	}

	public string USPAGE
	{
		get
		{
			return uspage;
		}
		set
		{
			if (!string.Equals(uspage, value, StringComparison.Ordinal))
			{
				uspage = value;
				OnPropertyChanged(<>PropertyChangedEventArgs.UpdateCommand);
				RaisePropertyChanged("USPAGE");
				CloseDevice();
			}
		}
	}

	public string StatusStyle
	{
		get
		{
			return statusStyle;
		}
		set
		{
			if (!string.Equals(statusStyle, value, StringComparison.Ordinal))
			{
				statusStyle = value;
				RaisePropertyChanged("StatusStyle");
			}
		}
	}

	public int ProgressBar
	{
		get
		{
			return progressBar;
		}
		set
		{
			if (progressBar != value)
			{
				progressBar = value;
				RaisePropertyChanged("ProgressBar");
			}
		}
	}

	public string BinFullPath
	{
		get
		{
			return binFullPath;
		}
		set
		{
			if (!string.Equals(binFullPath, value, StringComparison.Ordinal))
			{
				binFullPath = value;
				RaisePropertyChanged("BinFullPath");
			}
		}
	}

	public string Status
	{
		get
		{
			return status;
		}
		set
		{
			if (!string.Equals(status, value, StringComparison.Ordinal))
			{
				status = value;
				RaisePropertyChanged("Status");
			}
		}
	}

	public string StartBackground
	{
		get
		{
			return startBackground;
		}
		set
		{
			if (!string.Equals(startBackground, value, StringComparison.Ordinal))
			{
				startBackground = value;
				RaisePropertyChanged("StartBackground");
			}
		}
	}

	public string StatusForeground
	{
		get
		{
			return statusForeground;
		}
		set
		{
			if (!string.Equals(statusForeground, value, StringComparison.Ordinal))
			{
				statusForeground = value;
				RaisePropertyChanged("StatusForeground");
			}
		}
	}

	public bool IsShowUpgrade
	{
		get
		{
			return isShowUpgrade;
		}
		set
		{
			if (isShowUpgrade != value)
			{
				isShowUpgrade = value;
				OnPropertyChanged(<>PropertyChangedEventArgs.IsShowUpgrade);
			}
		}
	}

	public bool IsShowProcess
	{
		get
		{
			return isShowProcess;
		}
		set
		{
			if (isShowProcess != value)
			{
				isShowProcess = value;
				OnPropertyChanged(<>PropertyChangedEventArgs.IsShowProcess);
			}
		}
	}

	public bool IsShowSuccess
	{
		get
		{
			return isShowSuccess;
		}
		set
		{
			if (isShowSuccess != value)
			{
				isShowSuccess = value;
				OnPropertyChanged(<>PropertyChangedEventArgs.IsShowSuccess);
			}
		}
	}

	public bool IsShowError
	{
		get
		{
			return isShowError;
		}
		set
		{
			if (isShowError != value)
			{
				isShowError = value;
				OnPropertyChanged(<>PropertyChangedEventArgs.IsShowError);
			}
		}
	}

	public FirmwareApiModel FirmwareModel
	{
		get
		{
			return firmwareModel;
		}
		set
		{
			if (!object.Equals(firmwareModel, value))
			{
				firmwareModel = value;
				RaisePropertyChanged("FirmwareModel");
			}
		}
	}

	public FDGDeviceInfo CurrentFDGDeviceInfo
	{
		get
		{
			return currentFDGDeviceInfo;
		}
		set
		{
			if (!object.Equals(currentFDGDeviceInfo, value))
			{
				currentFDGDeviceInfo = value;
				OnPropertyChanged(<>PropertyChangedEventArgs.UpdateCommand);
				RaisePropertyChanged("CurrentFDGDeviceInfo");
			}
		}
	}

	public DelegateCommand CloseCommand => _CloseCommand ?? (_CloseCommand = new DelegateCommand(ExecuteCloseCommand));

	public DelegateCommand RetryCommand => _RetryCommand ?? (_RetryCommand = new DelegateCommand(ExecuteRetryCommand));

	public DelegateCommand<string> UpdateCommand => _UpdateCommand ?? (_UpdateCommand = new DelegateCommand<string>(ExecuteUpdateCommand));

	public bool IsLoading
	{
		get
		{
			return _IsLoading;
		}
		set
		{
			if (_IsLoading != value)
			{
				_IsLoading = value;
				OnPropertyChanged(<>PropertyChangedEventArgs.IsLoading);
			}
		}
	}

	public bool IsShowSuccessInfo
	{
		get
		{
			return isShowSuccessInfo;
		}
		set
		{
			if (isShowSuccessInfo != value)
			{
				isShowSuccessInfo = value;
				OnPropertyChanged(<>PropertyChangedEventArgs.IsShowSuccessInfo);
			}
		}
	}

	public bool IsShowFailedInfo
	{
		get
		{
			return isShowFailedInfo;
		}
		set
		{
			if (isShowFailedInfo != value)
			{
				isShowFailedInfo = value;
				OnPropertyChanged(<>PropertyChangedEventArgs.IsShowFailedInfo);
			}
		}
	}

	public string SuccessInfo
	{
		get
		{
			return successInfo;
		}
		set
		{
			if (!string.Equals(successInfo, value, StringComparison.Ordinal))
			{
				successInfo = value;
				OnPropertyChanged(<>PropertyChangedEventArgs.FailedInfo);
				OnPropertyChanged(<>PropertyChangedEventArgs.SuccessInfo);
			}
		}
	}

	public string FailedInfo
	{
		get
		{
			return successInfo;
		}
		set
		{
			if (!string.Equals(failedInfo, value, StringComparison.Ordinal))
			{
				successInfo = value;
				OnPropertyChanged(<>PropertyChangedEventArgs.FailedInfo);
			}
		}
	}

	public string TipInfo
	{
		get
		{
			return _TipInfo;
		}
		set
		{
			if (!string.Equals(_TipInfo, value, StringComparison.Ordinal))
			{
				_TipInfo = value;
				RaisePropertyChanged("TipInfo");
			}
		}
	}

	public bool IsShowTipInfo
	{
		get
		{
			return _IsShowTipInfo;
		}
		set
		{
			if (_IsShowTipInfo != value)
			{
				_IsShowTipInfo = value;
				RaisePropertyChanged("IsShowTipInfo");
			}
		}
	}

	public bool IsHideCLoseButton
	{
		get
		{
			return _IsHideCLoseButton;
		}
		set
		{
			if (_IsHideCLoseButton != value)
			{
				_IsHideCLoseButton = value;
				OnPropertyChanged(<>PropertyChangedEventArgs.IsHideCLoseButton);
			}
		}
	}

	public string LoadingTipInfo
	{
		get
		{
			return _LoadingTipInfo;
		}
		set
		{
			if (!string.Equals(_LoadingTipInfo, value, StringComparison.Ordinal))
			{
				_LoadingTipInfo = value;
				RaisePropertyChanged("LoadingTipInfo");
			}
		}
	}

	public string UpgradeButtonText
	{
		get
		{
			return _UpgradeButtonText;
		}
		set
		{
			if (!string.Equals(_UpgradeButtonText, value, StringComparison.Ordinal))
			{
				_UpgradeButtonText = value;
				RaisePropertyChanged("UpgradeButtonText");
			}
		}
	}

	public event Action<IDialogResult> RequestClose;

	public event Action CloseRequest;

	public FmUpgradeSwViewModel(string deviceType, bool IsForce = false, bool isHSH = false)
	{
		IsHSH = isHSH;
		IsFoundDevice = false;
		IsHideCLoseButton = !IsForce;
		CurrentFDGDeviceInfo = UniqueData.SelFDGDeviceInfo;
		MainPic = "\\Assets\\Resources\\product\\" + CurrentFDGDeviceInfo.ResName + "\\main.png";
		StartBackground = "#3F3F3F";
		StatusForeground = "#00ffff";
		string langKey = "GamePad_" + CurrentFDGDeviceInfo.ResName.ToUpper();
		ProductName = GamePadConfig.GetGamepadName(langKey, CurrentFDGDeviceInfo.ShowGameHadleName);
		findDev_flag = false;
		USPAGE = "FFEF";
		UpgradeButtonText = StrResources.Upgrade_checking;
		if (CurrentFDGDeviceInfo == null)
		{
			return;
		}
		CpuType = CurrentFDGDeviceInfo.CpuType;
		if (deviceType.ToLower() == "dongle")
		{
			if (IsHSH)
			{
				USPAGE = "FFB1";
			}
			else
			{
				USPAGE = "FFEE";
			}
			CpuType = "ch571";
			MainPic = "\\Assets\\Resources\\images\\product\\common\\dongle.png";
			ProductName = StrResources.Upgrade_Dongle;
		}
		new Task(async () =>
		{
			ExecDownloadFile();
		}).Start();
		IsShowUpgrade = true;
		IsShowProcess = false;
		IsShowSuccess = false;
		IsShowError = false;
		UpdateErrorMsg(isShow: false, "");
		if (CurrentFDGDeviceInfo.ConnectMode.ToLower() == "xinput")
		{
			UpgradeButtonText = StrResources.Upgrad_button;
			StartBackground = "#0074FF";
		}
		else
		{
			SetTimer();
		}
		if (CpuType != "ch571" && CurrentFDGDeviceInfo.ConnectType == FDGConncetType.wireless)
		{
			UpdateErrorMsg(isShow: true, StrResources.Upgrade_1tishi);
			StartBackground = "#0074ff";
		}
		if (IsHSH && CurrentFDGDeviceInfo?.ConnectMode == "DInput")
		{
			GamePadModeService.SwitchMode("dinput_ota");
		}
	}

	public void SetIsHSH(bool isHSH)
	{
		IsHSH = isHSH;
	}

	public void UpdateErrorMsg(bool isShow, string msg)
	{
		IsShowTipInfo = isShow;
		TipInfo = msg;
	}

	public bool CanCloseDialog()
	{
		return true;
	}

	public void OnDialogClosed()
	{
	}

	public void OnDialogOpened(IDialogParameters parameters)
	{
	}

	private void ExecuteCloseCommand()
	{
		checkTimer?.Stop();
		checkTimer?.Close();
		Task.Run(async () =>
		{
			FLog.d("【FirmwareUpgrade】：ExecuteCloseCommand");
			MainWindowViewModel.fmSwUpgradeView = null;
			FLog.d("【FirmwareUpgrade】：Change XInput Mode Start");
			FmUpgradeNotice.NoticeFMUpgrade(isFmUpgrade: true);
			MainWindowUpdateLoading(IsOpen: true, StrResources.Upgrade_modeloading);
			await Task.Delay(2000);
			GamePadInfoService.GetGamepadInfo();
			if (UniqueData.SelFDGDeviceInfo != null && UniqueData.IsDInput())
			{
				GamePadModeService.SwitchMode("XInput");
			}
			await Task.Delay(2000);
			MainWindowUpdateLoading(IsOpen: false);
			FLog.d("【FirmwareUpgrade】：Change XInput Mode Over");
			UniqueData.IsFirmwareUpdating = false;
		});
		checkTimer?.Stop();
		checkTimer?.Close();
		CloseRequest?.Invoke();
		MainWindowViewModel.fmSwUpgradeView = null;
	}

	private void ExecuteRetryCommand()
	{
		lock (lockobj)
		{
			new Task(async () =>
			{
				await Task.Delay(1000);
				if (!UniqueData.IsConnected)
				{
					StartBackground = "#3F3F3F";
					UpdateErrorMsg(isShow: true, StrResources.Upgrade_Erro_Tip2);
					Task.Delay(1000).ContinueWith((Task t) =>
					{
						ExecuteRetryCommand();
					}).ConfigureAwait(continueOnCapturedContext: false);
				}
				else
				{
					ShowUpgrading();
					if (IsHSH)
					{
						await Task.Delay(200);
						if (CurrentFDGDeviceInfo?.ConnectMode == "XInput")
						{
							GamePadModeService.SwitchMode("xinput_ota");
						}
						else if (CurrentFDGDeviceInfo?.ConnectMode == "DInput")
						{
							GamePadModeService.SwitchMode("dinput_ota");
						}
					}
					while (!findDev_flag)
					{
						await Task.Delay(50);
					}
					UpdateErrorMsg(isShow: true, "");
					ExecuteStartWrite();
				}
			}).Start();
		}
	}

	private void ExecuteUpdateCommand(string uspageType)
	{
		if (UniqueData.SelFDGDeviceInfo != null && CpuType != "ch571" && UniqueData.SelFDGDeviceInfo.ConnectType == FDGConncetType.wireless)
		{
			ShowError(StrResources.Upgrade_Erro_Tip1);
		}
		if (UniqueData.SelFDGDeviceInfo != null && CpuType == "ch571" && UniqueData.SelFDGDeviceInfo.ConnectType == FDGConncetType.wired)
		{
			ShowError(StrResources.Error_tip1);
		}
		if (!findDev_flag)
		{
			if (IsHSH)
			{
				if (CurrentFDGDeviceInfo?.ConnectMode == "XInput")
				{
					GamePadModeService.SwitchMode("xinput_ota");
				}
				else if (CurrentFDGDeviceInfo?.ConnectMode == "DInput")
				{
					GamePadModeService.SwitchMode("dinput_ota");
				}
			}
			else if (CurrentFDGDeviceInfo?.ConnectMode == "XInput")
			{
				GamePadModeService.SwitchMode("DInput");
			}
			SetTimer();
		}
		IsShowProcess = true;
		IsShowUpgrade = false;
		new Task(() =>
		{
			while (!findDev_flag)
			{
				Task.Delay(100);
			}
			IsShowSuccess = false;
			IsShowError = false;
			UniqueData.IsFirmwareUpdating = true;
			ServerLogService.SetCheckStatus(isOpen: false);
			FLog.d("【FirmwareUpgrade】：Start Upgrade Firmware");
			Task.Delay(2000).ContinueWith((Task t) =>
			{
				FLog.d("【FirmwareUpgrade】：Start Upgrade Firmware：delay 1000ms");
				ExecuteStartWrite();
			});
		}).Start();
	}

	private void SetTimer()
	{
		checkTimer = new Timer(1000.0);
		checkTimer.AutoReset = true;
		checkTimer.Enabled = true;
		checkTimer.Elapsed += TimerUp;
		checkTimer.Start();
		Task.Delay(3000).ContinueWith((Task t) =>
		{
			if (!findDev_flag)
			{
				if (CpuType == "ch571")
				{
					UpdateErrorMsg(isShow: true, StrResources.Upgrade_2tishi);
				}
				else
				{
					UpdateErrorMsg(isShow: true, StrResources.Upgrade_1tishi);
				}
			}
		});
	}

	private void TimerUp(object sender, ElapsedEventArgs e)
	{
		try
		{
			if (findDev_flag)
			{
				checkTimer.Stop();
			}
			else if (!IsUpgradeSuccess)
			{
				USB_SearchDevice();
			}
		}
		catch (Exception ex)
		{
			FLog.LogException(ex);
			ALiErrLogUtils.SendLogToServer(ex);
			FLog.d("【FirmwareUpgrade】：TimerUpNew ERROR:" + ex.Message);
		}
	}

	private bool USB_SearchDevice()
	{
		if (findDev_flag)
		{
			return findDev_flag;
		}
		FLog.d("【FirmwareUpgrade】：USB_SearchDevice");
		string allDevPath = "";
		string allHandleDevPath = "";
		string searchHandleDevPath = "";
		string hidpCaps = "";
		string value = "04B4";
		string value2 = "2412";
		hWriteDevHandle = -1;
		hReadDevHandle = -1;
		InputReportByteLength = 0;
		OutputReportByteLength = 0;
		FeatureReportByteLength = 0;
		ushort vid = Convert.ToUInt16(value, 16);
		ushort pid = Convert.ToUInt16(value2, 16);
		ushort usagePage = Convert.ToUInt16(USPAGE, 16);
		byte b = 0;
		if (USPAGE == "FFB1")
		{
			b = 1;
		}
		findDev_flag = UsbAPI.FindDeviceNew(vid, pid, usagePage, b, ref hReadDevHandle, ref hWriteDevHandle, ref InputReportByteLength, ref OutputReportByteLength, ref FeatureReportByteLength, ref hidpCaps, ref allDevPath, ref allHandleDevPath, ref searchHandleDevPath);
		FLog.d($"findDev_flag:{findDev_flag}_usPage:{USPAGE}_uspage:{b}");
		if (findDev_flag && InputReportByteLength > 0)
		{
			hidDevice = new FileStream(new SafeFileHandle((IntPtr)hReadDevHandle, ownsHandle: false), FileAccess.ReadWrite, InputReportByteLength, isAsync: true);
			BeginAsyncRead();
			FLog.d($"findDev_flag:{findDev_flag}_usPage:{USPAGE}_uspage:{b}_InputReportByteLength:{InputReportByteLength}");
			checkTimer.Stop();
			UpgradeButtonText = StrResources.Upgrad_button;
			FLog.d("【FirmwareUpgrade】：Found Device" + StrResources.Upgrad_button);
			IsFoundDevice = true;
			for (int i = 0; i < OutputReportByteLength; i++)
			{
				DefaultSendBytes[i] = byte.MaxValue;
			}
			Status = "连接成功";
			StatusStyle = "ButtonSuccess";
			StartBackground = "#0074ff";
			StatusForeground = "#0074ff";
		}
		if (InputReportByteLength <= 0)
		{
			findDev_flag = false;
		}
		return findDev_flag;
	}

	private void ExecuteStartWrite()
	{
		FLog.d("【FirmwareUpgrade】：Execute Start Write :0");
		if (!check_bin_is_ok())
		{
			return;
		}
		FLog.d("【FirmwareUpgrade】：Execute Start Write :1");
		if (start_ota_flag <= 0)
		{
			FLog.d("【FirmwareUpgrade】：Execute Start Write :2");
			if (!findDev_flag)
			{
				FLog.d("【FirmwareUpgrade】：device disconnect");
				return;
			}
			FLog.d("【FirmwareUpgrade】：Execute Start Write :3");
			upgradeLoading(isOpen: true);
			IsHideCLoseButton = false;
			ota_index = 0;
			start_ota_flag = 1;
			FLog.d("【FirmwareUpgrade】：Execute Start Write :Start");
			ota_write();
		}
	}

	private bool check_bin_is_ok()
	{
		if (bin_crc == uint.MaxValue || bin_crc == 0)
		{
			string text = "【FirmwareUpgrade】：Firmware CRC is wrong，illegal firmware";
			FLog.d(text);
			return false;
		}
		return true;
	}

	public void upgradeLoading(bool isOpen)
	{
	}

	public void UpdateUI(bool isSuccess)
	{
		if (isSuccess)
		{
			IsShowUpgrade = false;
			IsShowProcess = false;
			IsShowSuccess = true;
			IsShowError = false;
			Task.Run(async () =>
			{
				UpdateLoading(IsOpen: true, StrResources.Upgrade_connectloading);
				await Task.Delay(10000);
				UpdateLoading(IsOpen: false);
			});
		}
		else
		{
			IsShowUpgrade = false;
			IsShowProcess = false;
			IsShowSuccess = false;
			IsShowError = true;
		}
	}

	public void ShowSuccess(string msg)
	{
		IsShowSuccessInfo = true;
		SuccessInfo = msg;
		Task.Run(async () =>
		{
			await Task.Delay(2000);
			IsShowSuccessInfo = false;
			SuccessInfo = "";
		});
	}

	public void ShowError(string msg)
	{
		IsShowFailedInfo = true;
		FailedInfo = msg;
		Task.Run(async () =>
		{
			await Task.Delay(2000);
			IsShowFailedInfo = false;
			FailedInfo = "";
		});
	}

	public void UpdateLoading(bool IsOpen, string msg = "")
	{
		IsLoading = IsOpen;
		LoadingTipInfo = msg;
	}

	public void MainWindowUpdateLoading(bool IsOpen, string msg = "")
	{
		MainWindowViewModel.GetInstance().LoaddingAndMsg(IsOpen, msg);
	}

	private async void ota_write()
	{
		bool need_send = false;
		byte[] sendbuf = new byte[60];
		sendLists = sendBytes.ToList();
		int start = 3;
		sendLists[0] = 2;
		if (start_ota_flag == 1)
		{
			sendLists[1] = 2;
			sendLists[2] = 0;
			sendLists[start] = 1;
			sendLists[start + 1] = byte.MaxValue;
			ota_index = 0;
			start_ota_flag = 2;
			otaStartTime = DateTime.Now;
			need_send = true;
		}
		else if (start_ota_flag == 2)
		{
			need_send = true;
			sendLists[1] = 0;
			sendLists[2] = 0;
			byte[] crc_src_buf = new byte[18];
			for (int col = 0; col < 3; col++)
			{
				sendbuf[20 * col] = (byte)(ota_index & 0xFF);
				sendbuf[20 * col + 1] = (byte)((ota_index >> 8) & 0xFF);
				crc_src_buf[0] = sendbuf[20 * col];
				crc_src_buf[1] = sendbuf[20 * col + 1];
				for (int i = 0; i < 16; i++)
				{
					sendbuf[20 * col + i + 2] = source_binchar[ota_index * 16 + i];
					crc_src_buf[i + 2] = source_binchar[ota_index * 16 + i];
				}
				ushort crc = FirmwareUpgradeUtils.crc16(crc_src_buf, 18);
				sendbuf[20 * col + 18] = (byte)(crc & 0xFF);
				sendbuf[20 * col + 19] = (byte)((crc >> 8) & 0xFF);
				ota_index++;
				if (ota_index * 16 >= source_bin_size + 16)
				{
					ota_index--;
					break;
				}
				sendLists[1] = (byte)(20 * col + 20);
			}
			for (int j = 0; j < sendLists[1]; j++)
			{
				sendLists[start + j] = sendbuf[j];
			}
			ota_jindu = ota_index * 16 * 100 / source_bin_size;
			Task.Delay(4000).ContinueWith((Task t) =>
			{
				if (ota_jindu == 0)
				{
					UpdateErrorMsg(isShow: true, StrResources.Upgrade_0tishi);
				}
				else
				{
					UpdateErrorMsg(isShow: false, "");
				}
				if (UniqueData.SelFDGDeviceInfo != null && UniqueData.SelFDGDeviceInfo.ConnectMode.ToLower() == "xinput" && ota_jindu == 0)
				{
					UpdateErrorMsg(isShow: true, StrResources.Upgrade_3tishi);
				}
			});
			if (ota_jindu == 90)
			{
			}
			if (ota_jindu >= 100)
			{
				await Task.Delay(1000);
				ota_jindu = 100L;
			}
			ProgressBar = (int)ota_jindu;
			if (sendLists[1] == 0)
			{
				FLog.d("【FirmwareUpgrade】：times:" + (DateTime.Now - otaStartTime).TotalSeconds);
				sendLists[1] = 6;
				sendLists[2] = 0;
				sendLists[start] = 2;
				sendLists[start + 1] = byte.MaxValue;
				ushort temp_ota_index = (ushort)(ota_index - 1);
				sendLists[start + 2] = (byte)(temp_ota_index & 0xFF);
				sendLists[start + 3] = (byte)((temp_ota_index >> 8) & 0xFF);
				ushort ww = (ushort)(65535 - temp_ota_index + 1);
				sendLists[start + 4] = (byte)(ww & 0xFF);
				sendLists[start + 5] = (byte)((ww >> 8) & 0xFF);
				start_ota_flag = 0;
				ota_index = 0;
				Status = "升级成功";
				FmUpgradeNotice.NoticeFMUpgrade(isFmUpgrade: true);
				checkTimer.Stop();
				checkTimer.Close();
				StartBackground = "#98FB98";
				StatusForeground = "#98FB98";
				upgradeLoading(isOpen: false);
				UpdateUI(isSuccess: true);
				IsUpgradeSuccess = true;
				FLog.d("【FirmwareUpgrade】：Upgrade Success!");
			}
		}
		if (need_send)
		{
			int errNum = 0;
			string errReason = "";
			sendLists.RemoveAt(sendLists.Count - 1);
			sendLists.Insert(0, report_id);
			user_sendDataToDevice(SENDTYPE.WRITE, sendLists.ToArray(), OutputReportByteLength, ref errNum, ref errReason);
			if (errNum != 0)
			{
				Status = "errNum:" + errNum + errReason;
				UpdateUI(isSuccess: false);
			}
		}
	}

	private bool user_sendDataToDevice(SENDTYPE sendType, byte[] buf, int len, ref int errNum, ref string errReason)
	{
		if (!findDev_flag)
		{
			return false;
		}
		int num = 0;
		Array.Clear(sendReportDataBuf, 0, len);
		sendReportDataBuf = buf;
		bool flag = false;
		switch (sendType)
		{
		case SENDTYPE.FEATURE:
			num = FeatureReportByteLength;
			flag = UsbAPI.HidD_SetFeature(new IntPtr(hWriteDevHandle), sendReportDataBuf, num);
			if (!flag)
			{
				errNum = UsbAPI.GetLastError();
				errReason = UsbAPI.GetSysErrMsg(errNum);
				FLog.d("【FirmwareUpgrade】：SetFeatureReport Fail->[" + errNum + "]" + errReason);
			}
			else
			{
				FLog.d("【FirmwareUpgrade】：SetFeatureReport success");
			}
			break;
		case SENDTYPE.OUTPUT:
			num = OutputReportByteLength;
			flag = UsbAPI.HidD_SetOutputReport((IntPtr)hWriteDevHandle, sendReportDataBuf, num);
			if (!flag)
			{
				errNum = UsbAPI.GetLastError();
				errReason = UsbAPI.GetSysErrMsg(errNum);
				FLog.d("【FirmwareUpgrade】：SetOutputReport Fail->[" + errNum + "]");
			}
			else
			{
				FLog.d("【FirmwareUpgrade】： SetOutputReport Success");
			}
			break;
		case SENDTYPE.WRITE:
			try
			{
				hidDevice.Write(sendReportDataBuf, 0, OutputReportByteLength);
			}
			catch (Exception ex)
			{
				FLog.LogException(ex);
				ALiErrLogUtils.SendLogToServer(ex);
				IsShowUpgrade = false;
				IsShowProcess = false;
				IsShowSuccess = false;
				IsShowError = true;
				UniqueData.IsFirmwareUpdating = false;
			}
			break;
		}
		return flag;
	}

	public async void ExecDownloadFile()
	{
		try
		{
			string firmwareName = CurrentFDGDeviceInfo.FirmwareName;
			if (CpuType == "ch571")
			{
				firmwareName = CurrentFDGDeviceInfo.DONGLEFirmwareName;
			}
			if (CpuType == "ch571")
			{
				FirmwareModel = FirmwareService.GetFirmware(firmwareName, CpuType, CurrentFDGDeviceInfo.DongleVersion);
			}
			else
			{
				FirmwareModel = FirmwareService.GetFirmware(firmwareName, CpuType, CurrentFDGDeviceInfo.FirmwareVersion);
			}
			if (FirmwareModel == null)
			{
				return;
			}
			string BinDownLoadUrl = FirmwareModel.url;
			if (string.IsNullOrEmpty(BinDownLoadUrl))
			{
				return;
			}
			string fileExtension = Path.GetExtension(BinDownLoadUrl);
			Uri fileUri = new Uri(BinDownLoadUrl);
			string fileName = Path.GetFileName(fileUri.LocalPath);
			if (!fileExtension.Equals(".zip", StringComparison.OrdinalIgnoreCase))
			{
				return;
			}
			string localFilePath = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.InternetCache), fileName);
			string targetDirectory = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.InternetCache), "FlydigiFirmwareDownload\\" + TimeUtils.GetCurrentUnixTimestampMillis());
			await FirmwareService.DownloadFileAsync(BinDownLoadUrl, localFilePath);
			FirmwareService.ExtractZipFile(localFilePath, targetDirectory);
			using (IEnumerator<string> enumerator = Directory.EnumerateFiles(targetDirectory, "*.bin").GetEnumerator())
			{
				if (enumerator.MoveNext())
				{
					string filePath = enumerator.Current;
					BinFullPath = filePath;
				}
			}
			if (BinFullPath != null)
			{
				byte[] H = new byte[524288];
				uint length = 0u;
				FirmwareUpgradeUtils.ReadBinFile(BinFullPath, ref H, ref length);
				source_bin_size = BitConverter.ToUInt32(H, 24);
				bin_crc = BitConverter.ToUInt32(H, (int)(source_bin_size - 4));
				for (int i = 0; i < source_bin_size; i++)
				{
					source_binchar[i] = H[i];
				}
				for (int j = 0; j < 16; j++)
				{
					source_binchar[source_bin_size + j] = byte.MaxValue;
				}
				bin_fw_version = BitConverter.ToUInt32(H, 2);
				string bin_inf_label = "Firmware Verson=0x" + bin_fw_version.ToString("X2") + "\r\ncode_Size=" + source_bin_size + "(0x" + source_bin_size.ToString("X") + ")code_crc=" + bin_crc.ToString("X2");
				FLog.d("【FirmwareUpgrade】：" + bin_inf_label);
			}
		}
		catch (Exception ex)
		{
			Exception e = ex;
			FLog.LogException(e);
			ALiErrLogUtils.SendLogToServer(e);
			FLog.d("【FirmwareUpgrade】：telink bin File format error");
		}
	}

	private void ReadCompleted(IAsyncResult iResult)
	{
		byte[] array = (byte[])iResult.AsyncState;
		if (hidDevice == null)
		{
			return;
		}
		try
		{
			hidDevice.EndRead(iResult);
			for (int i = 0; i < array.Length; i++)
			{
				readFileDataBuf[i] = array[i];
			}
			Task task = new Task(() =>
			{
				Read_File_Data_Process_YKQ();
			});
			task.Start();
			if (findDev_flag)
			{
				BeginAsyncRead();
			}
		}
		catch (Exception ex)
		{
			ALiErrLogUtils.SendLogToServer(ex);
			EventArgs e = new EventArgs();
			OnDeviceRemoved(e);
		}
	}

	private void Read_File_Data_Process_YKQ()
	{
		//IL_0144: Unknown result type (might be due to invalid IL or missing references)
		try
		{
			bool flag = true;
			if (readFileDataBuf[0] == 5 && readFileDataBuf[1] == 2 && readFileDataBuf[2] == 3 && readFileDataBuf[3] == 0 && readFileDataBuf[4] == 6 && readFileDataBuf[5] == byte.MaxValue)
			{
				if (readFileDataBuf[6] == 0)
				{
					FLog.d("OTA Success");
				}
				else
				{
					flag = false;
					string text = "OTA Fail=" + readFileDataBuf[6];
					FLog.d(text);
				}
			}
			else if (get_fw_version && readFileDataBuf[0] == 5 && readFileDataBuf[1] == 1 && readFileDataBuf[2] == 8 && readFileDataBuf[3] == 0)
			{
				string text2 = "Version=0x" + BitConverter.ToUInt32(readFileDataBuf, 4).ToString("X2") + "\r\n";
				text2 = text2 + "CRC=0x" + BitConverter.ToUInt32(readFileDataBuf, 8).ToString("X2");
				FLog.d(text2);
				MessageBox.Show(text2, "USB Device Firmware Inforamtion");
			}
			if (start_ota_flag == 0 || readFileDataBuf[0] != 5)
			{
			}
			if (flag && start_ota_flag != 0)
			{
				ota_write();
			}
		}
		catch (Exception ex)
		{
			FLog.LogException(ex);
			ALiErrLogUtils.SendLogToServer(ex);
			FLog.d("【FirmwareUpgrade】：progress error");
			upgradeLoading(isOpen: false);
		}
	}

	private void OnDeviceRemoved(EventArgs e)
	{
		CloseDevice();
	}

	public void CloseDevice()
	{
		if (findDev_flag)
		{
			findDev_flag = false;
			if (hidDevice != null)
			{
				hidDevice.Close();
			}
			checkTimer.Stop();
			start_ota_flag = 0;
			checkTimer.Start();
			Status = "未连接";
			ProgressBar = 0;
			StartBackground = "#3F3F3F";
			StatusForeground = "#FFFFFF";
			UpgradeButtonText = StrResources.Upgrade_checking;
			UniqueData.IsFirmwareUpdating = false;
			IsFoundDevice = false;
			if (!IsUpgradeSuccess)
			{
				ShowRetry();
			}
			upgradeLoading(isOpen: false);
		}
	}

	public void ShowRetry()
	{
		IsShowUpgrade = false;
		IsShowProcess = false;
		IsShowSuccess = false;
		IsShowError = true;
	}

	public void ShowUpgrading()
	{
		IsShowUpgrade = false;
		IsShowProcess = true;
		IsShowSuccess = false;
		IsShowError = false;
	}

	private void BeginAsyncRead()
	{
		byte[] array = new byte[InputReportByteLength];
		hidDevice.BeginRead(array, 0, InputReportByteLength, ReadCompleted, array);
	}

	public void Configure()
	{
		throw new NotImplementedException();
	}
}
