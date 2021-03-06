import wx
import time
import requests
import threading
import os
import shutil
import ConfigParser
import subprocess
import keyring
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import StringIO
import zipfile
import hashlib

s = requests.Session()
s.headers["User-Agent"] = "PMRClient 1.0.0"

stagedsaves = []

pmr_resources_path = "resources"

def_pmrpath = os.path.join(os.path.expanduser('~'),"Documents","SimCity 4","Plugins","_PMR") + "\\"
def_resw = 1280
def_resh = 800
def_sc4path = ""

PMR_LAUNCHPATH = None
PMR_LAUNCHRESW = None
PMR_LAUNCHRESH = None
PMR_SERVERPATH = "http://api.getpmr.com/"
PMR_CUSTOMPATH = None

def get_pmr_path(filename):
	return os.path.join(pmr_resources_path, filename)

def md5(fname):
	hash_md5 = hashlib.md5()
	with open(fname, "rb") as f:
		for chunk in iter(lambda: f.read(4096), b""):
			hash_md5.update(chunk)
	return hash_md5.hexdigest()

#pmrpath = os.path.realpath(__file__)

class PMRClient(wx.Frame):

	def __init__(self, parent):
		super(PMRClient, self).__init__(parent, style=wx.CAPTION | wx.CLOSE_BOX)
		self.Bind(EVT_SERVERSTATUSRESPONSE, self.onCheckServerReponse)
		self.Bind(EVT_LISTINGRESPONSE, self.FinishRefreshList)
		
		self.InitUI()
		self.Fit()
		self.Centre()
		self.Show()

		self.Prep()

		self.CheckServer()
		#self.ShowFirstRun()
		self.StartRefreshList()

		self.Bind(wx.EVT_CLOSE, self.onClose)

	def WarnError(parent, message, caption = 'Error!'):
		dlg = wx.MessageDialog(parent, message, caption, wx.OK | wx.ICON_ERROR)
		dlg.ShowModal()
		dlg.Destroy()

	def Warn(parent, message, caption = 'Important message from PMR'):
		dlg = wx.MessageDialog(parent, message, caption, wx.OK | wx.ICON_EXCLAMATION)
		dlg.ShowModal()
		dlg.Destroy()

	def Prep(self):
		global PMR_LAUNCHPATH
		global PMR_LAUNCHRESW
		global PMR_LAUNCHRESH
		global PMR_CUSTOMPATH
		
		# Load configuration file, or create one if it doesn't exist
		configpath = get_pmr_path("config.ini")
		try:
			config = ConfigParser.RawConfigParser()
			config.read(configpath)

			PMR_LAUNCHPATH = config.get('launcher', 'path')
			PMR_LAUNCHRESW = config.get('launcher', 'resw')
			PMR_LAUNCHRESH = config.get('launcher', 'resh')
			PMR_CUSTOMPATH = config.get('launcher', 'sc4path')
		except:
			config.remove_section('launcher')
			config.add_section('launcher')
			config.set('launcher', 'path', def_pmrpath)
			config.set('launcher', 'resw', def_resw)
			config.set('launcher', 'resh', def_resh)
			config.set('launcher', 'sc4path', def_sc4path)
			
			with open(configpath, 'wb') as configfile:
				config.write(configfile)

			PMR_LAUNCHPATH = def_pmrpath
			PMR_LAUNCHRESW = def_resw
			PMR_LAUNCHRESH = def_resh
			PMR_CUSTOMPATH = def_sc4path

			self.ShowFirstRun()

		# Create required directories
		directories = ["PMRCache", "PMRPluginsCache", "PMRSalvage", "Regions", "Plugins", os.path.join("Plugins","PMRPlugins")]

		for directory in directories:
			directorytocreate = os.path.join(PMR_LAUNCHPATH, directory)
			if not os.path.exists(directorytocreate):
				try:
					os.makedirs(directorytocreate)
				except:
					self.WarnError("The PMR Launcher could not start because it cannot write to its path\n\nPlease try again. If this error persists, try deleting the 'resources/config.ini' file.", "PMR Launcher could not start")
					self.onClose(None)
			if directory == "Plugins":
				noticepath = os.path.join(PMR_LAUNCHPATH, directory, "__PUT YOUR PLUGINS IN THIS FOLDER__.txt")
				open(noticepath, 'a').close()

	def InitUI(self):
		panel = wx.Panel(self)
		panel.SetBackgroundColour('#eeeeee')

		ico = wx.Icon(get_pmr_path('icon.ico'), wx.BITMAP_TYPE_ICO)
		self.SetIcon(ico)

		vbox = wx.BoxSizer(wx.VERTICAL)

		flag = wx.StaticBitmap(panel, wx.ID_ANY, wx.Bitmap(get_pmr_path("flag.png"), wx.BITMAP_TYPE_ANY))

		self.infotext = wx.StaticText(panel, label='To get started, select a region below and click \'Connect.\'', style=wx.ALIGN_CENTRE_HORIZONTAL | wx.ST_NO_AUTORESIZE)

		self.regionlist = wx.ListCtrl(panel, -1, style = wx.LC_REPORT, size=(-1,300)) 
		self.regionlist.InsertColumn(0, "Region Name", width=225)
		self.regionlist.InsertColumn(1, "Claimed Tiles", wx.LIST_FORMAT_RIGHT, width=100)
		self.regionlist.InsertColumn(2, "Mayors Online", wx.LIST_FORMAT_RIGHT, width=100)
		self.regionlist.Bind(wx.EVT_LIST_ITEM_SELECTED, self.SelectRegion)
		self.regionlist.Bind(wx.EVT_LIST_ITEM_DESELECTED, self.DeselectRegion)
		self.regionlist.Bind(wx.EVT_LIST_ITEM_ACTIVATED, self.ConnectToSelectedRegion)

		hbox = wx.BoxSizer(wx.HORIZONTAL)
		# versiontext = wx.StaticText(panel, label='PMR Launcher Release Candidate')
		# versiontext.SetForegroundColour((150,150,150))
		self.settingbtn = wx.Button(panel, label='SC4 Settings...')
		self.settingbtn.SetToolTip(wx.ToolTip("Set your preferred resolution and launch path"))
		self.settingbtn.Bind(wx.EVT_BUTTON, self.ShowSettingsDialog)
		self.refreshbtn = wx.Button(panel, label='Refresh')
		self.refreshbtn.Bind(wx.EVT_BUTTON, self.StartRefreshList)
		self.refreshbtn.SetToolTip(wx.ToolTip("Refresh the region listing"))
		self.connectbtn = wx.Button(panel, label='Connect')
		self.connectbtn.Bind(wx.EVT_BUTTON, self.ConnectToSelectedRegion)
		self.connectbtn.SetToolTip(wx.ToolTip("Connect to the selected region"))
		self.connectbtn.Disable()
		# hbox.Add(versiontext, 1, wx.ALIGN_LEFT | wx.ALIGN_CENTER_VERTICAL, 10)
		hbox.Add(self.settingbtn, 0, wx.RIGHT | wx.ALIGN_LEFT, 5)
		hbox.InsertStretchSpacer(1)
		hbox.Add(self.refreshbtn, 0, wx.RIGHT | wx.ALIGN_RIGHT, 5)
		hbox.Add(self.connectbtn, 0, wx.ALIGN_RIGHT, 10)

		vbox.Add(flag, 0, wx.ALL, 0)
		vbox.Add(self.infotext, 0, wx.EXPAND|wx.ALL, 10)
		vbox.Add(self.regionlist, 1, wx.EXPAND|wx.LEFT|wx.RIGHT, 10)
		vbox.Add(hbox, 0, wx.EXPAND|wx.ALL, 10)

		panel.SetSizer(vbox)
		panel.Fit()

		self.SetTitle("Poppy Multiplayer Regions")

	def CheckServer(self):
		worker = ServerStatusRequestThread(self)
		worker.start()

	def onCheckServerReponse(self, event):
		for notice in event.GetNotices():
			self.Warn(str(notice))

	def ShowFirstRun(self, event = None):
		#pmrpath = os.path.join(os.path.expanduser('~'),"Documents","SimCity 4","_PMR")

		#if not os.path.exists(pmrpath):
		#os.makedirs(pmrpath)
		firstrundialog = PMRClientFirstRun(None)
		firstrundialog.ShowModal()
		firstrundialog.Destroy()
		#return True
		#return False

	def StartRefreshList(self, event = None):
		self.infotext.SetLabel("Getting region list...")
		self.regionlist.DeleteAllItems()
		self.regionlist.Disable()
		self.refreshbtn.Disable()

		self.listworker = ListingRequestThread(self)
		self.listworker.setDaemon(True)
		self.listworker.start()

	def FinishRefreshList(self, event = None):
		self.listings = event.GetValue()
		i = 0

		for listing in self.listings:
			self.regionlist.Append([listing["name"], str(listing["notiles"] - listing["freetiles"]) + "/" + str(listing["notiles"]), str(listing["noonline"]) + "/" + str(listing["capacity"])])
			self.listings[i]["listctrlid"] = i;
			i += 1

		self.infotext.SetLabel("To get started, select a region below and click \'Connect.\'")
		self.regionlist.Enable()
		self.refreshbtn.Enable()

	def SelectRegion(self, event = None):
		self.selectedregion = event.m_itemIndex;
		self.connectbtn.Enable()

	def DeselectRegion(self, event = None):
		self.connectbtn.Disable()

	def ConnectToSelectedRegion(self, event = None):
		self.selectedregion = self.listings[self.selectedregion]
		self.connectbtn.Disable()
		authdialog = PMRClientAuthenticator(None, self.selectedregion)
		authresult = authdialog.ShowModal()
		authdialog.Destroy()

		if authresult == 1:
			downloaddialog = PMRClientRegionDownloader(None,self.selectedregion)
			downloadresult = downloaddialog.ShowModal()
			downloaddialog.Destroy()

			if downloadresult == 1:
				possiblepaths = [
					os.path.abspath(os.path.join("\\", "Program Files (x86)", "Steam", "steamapps", "common", "SimCity 4 Deluxe", "Apps", "SimCity 4.exe")),
					os.path.abspath(os.path.join("\\", "Program Files", "Steam", "steamapps", "common", "SimCity 4 Deluxe", "Apps", "SimCity 4.exe")),
					os.path.abspath(os.path.join("\\", "Program Files (x86)", "Maxis", "SimCity 4 Deluxe", "Apps", "SimCity 4.exe")),
					os.path.abspath(os.path.join("\\", "Program Files", "Maxis", "SimCity 4 Deluxe", "Apps", "SimCity 4.exe")),
					PMR_CUSTOMPATH,
					os.path.join(PMR_CUSTOMPATH, "SimCity 4.exe"),
					os.path.join(PMR_CUSTOMPATH, "Apps", "SimCity 4.exe")
				]

				execpath = None

				# if os.path.exists(os.path.join("\\", "Program Files (x86)", "Steam", "steamapps", "common", "SimCity 4 Deluxe")):
				# 	execpath = r'"C:\Program Files (x86)\Steam\Steam.exe"'
				# 	issteam = True
				# elif os.path.exists(os.path.join("\\", "Program Files", "Steam", "steamapps", "common", "SimCity 4 Deluxe")):
				# 	execpath = r'"C:\Program Files\Steam\Steam.exe"'
				# 	issteam = True
				# else:
				for possiblepath in possiblepaths:
					if possiblepath:
						if os.path.isfile(possiblepath):
							execpath = '"' + possiblepath + '"'
							break

				if not execpath:
					self.WarnError("SimCity 4 was not found\n\nThe PMR Launcher could not find your installation of SimCity 4. If you have installed it to a custom directory, please provide the full path to the 'SimCity 4.exe' file under 'SC4 Settings...'")
					self.ClearSelection()
					return False

				# args = [execpath, '-UserDir:' + PMR_LAUNCHPATH + '\\', '-intro:off', '-w', '-CustomResolution:enabled', '-r' + str(PMR_LAUNCHRESW) + 'x' + str(PMR_LAUNCHRESH) + 'x32']
				args = [execpath, ' -UserDir:"' + PMR_LAUNCHPATH + '"', ' -intro:off', ' -w', ' -CustomResolution:enabled', ' -r' + str(PMR_LAUNCHRESW) + 'x' + str(PMR_LAUNCHRESH) + 'x32']
				print args

# args = r'"C:\Program Files (x86)\Steam\Steam.exe" -applaunch 24780 -UserDir:"' + PMR_LAUNCHPATH + '" -intro:off -w -CustomResolution:enabled -r' + str(PMR_LAUNCHRESW) + 'x' + str(PMR_LAUNCHRESH) + 'x32'
# 					try:
# 						p = subprocess.Popen([args])
# 					except:
# 					self.WarnError("The PMR Launcher does not have permission to launch SimCity 4\n\nPlease try again, and run the launcher as an administrator if possible.")
# 					return False
				#p = subprocess.Popen([args])
				
				# if issteam:
				# 	flatargs = r'' + execpath + ' -applaunch 24780 -UserDir:"' + PMR_LAUNCHPATH + '" -intro:off -w -CustomResolution:enabled -r' + str(PMR_LAUNCHRESW) + 'x' + str(PMR_LAUNCHRESH) + 'x32'
				# 	try:
				# 		subprocess.call(flatargs, shell=False)
				# 	except:
				# 		self.WarnError("The PMR Launcher does not have permission to launch SimCity 4\n\nPlease make sure SimCity 4 is not already running and try again. You should also try to run the launcher as an administrator if possible.")
				# 		return False
				# else:
				try:
					p = subprocess.Popen([args])
				except:
					self.WarnError("The PMR Launcher does not have permission to launch SimCity 4\n\nPlease make sure SimCity 4 is not already running and try again. You should also try to run the launcher as an administrator if possible.")
					self.ClearSelection()
					return False

				regioninspector = PMRClientRegionInspector(None,self.selectedregion)
				self.Hide()
			elif downloadresult == -1:
				self.WarnError("The region couldn't be downloaded at this moment\n\nPlease try connecting again.", "Region download failed")

		for x in xrange(0, self.regionlist.GetItemCount(), 1):
			self.regionlist.Select(x, on=0)

	def ShowSettingsDialog(self, event = None):
		settingsdialog = PMRClientSettings(None)
		settingsdialog.ShowModal()
		settingsdialog.Destroy()

	def onClose(self, event):
		#self.listworker.join(5)
		wx.Exit()

	def ClearSelection(self):
		for x in xrange(0, self.regionlist.GetItemCount(), 1):
			self.regionlist.Select(x, on=0)

class PMRClientSettings(wx.Dialog):
	def __init__(self, parent):
		super(PMRClientSettings, self).__init__(parent, style=wx.CAPTION)
		self.InitUI()
		self.PopulateCurrentSettings()
		self.Fit()
		self.Centre()
		self.Show()

	def WarnError(parent, message, caption = 'Error!'):
		dlg = wx.MessageDialog(parent, message, caption, wx.OK | wx.ICON_ERROR)
		dlg.ShowModal()
		dlg.Destroy()

	def InitUI(self):
		panel = wx.Panel(self)
		panel.SetBackgroundColour('#eeeeee')

		vbox = wx.BoxSizer(wx.VERTICAL)

		pmrpathlabel = wx.StaticText(panel, label='PMR Working Path:')
		self.pmrpathtc = wx.TextCtrl(panel)
		pmrpathwarn = wx.StaticText(panel, label="Do NOT change this to your normal launch directory, or else your regions will be deleted!")
		font = pmrpathwarn.GetFont()
		font.SetPointSize(8)
		font.SetWeight(wx.FONTWEIGHT_BOLD)
		pmrpathwarn.SetFont(font)
		pmrpathwarn.Wrap(300)

		resolutionlbl = wx.StaticText(panel, label='Custom Resolution:')
		hbox = wx.BoxSizer(wx.HORIZONTAL)
		self.reswtc = wx.TextCtrl(panel)
		resdivider = wx.StaticText(panel, label='by')
		self.reshtc = wx.TextCtrl(panel)
		hbox.Add(self.reswtc, 1, wx.ALL, 0)
		hbox.Add(resdivider, 0, wx.LEFT | wx.RIGHT | wx.ALIGN_CENTER_VERTICAL, 5)
		hbox.Add(self.reshtc, 1, wx.ALL, 0)
		resolutioninfo = wx.StaticText(panel, label="When choosing your custom resolution, remember that the PMR Launcher always starts SimCity 4 in windowed mode.")
		font = resolutioninfo.GetFont()
		font.SetPointSize(8)
		resolutioninfo.SetFont(font)
		resolutioninfo.Wrap(300)

		sc4pathlabel = wx.StaticText(panel, label='Path to \'SimCity 4.exe\':')
		self.sc4pathtc = wx.TextCtrl(panel)
		sc4pathinfo = wx.StaticText(panel, label="If the PMR Launcher cannot find 'SimCity 4.exe' in the most common installation paths, it will try using this value. You should only change this if you have installed SimCity 4 to a custom directory.")
		font = sc4pathinfo.GetFont()
		font.SetPointSize(8)
		sc4pathinfo.SetFont(font)
		sc4pathinfo.Wrap(300)

		hbox2 = wx.BoxSizer(wx.HORIZONTAL)
		self.cancelbtn = wx.Button(panel, label='Cancel')
		self.cancelbtn.Bind(wx.EVT_BUTTON, self.onCancel)
		self.savebtn = wx.Button(panel, label='Save')
		self.savebtn.Bind(wx.EVT_BUTTON, self.onSave)
		self.savebtn.SetFocus()
		hbox2.InsertStretchSpacer(0)
		hbox2.Add(self.cancelbtn, 0, wx.RIGHT | wx.ALIGN_RIGHT, 5)
		hbox2.Add(self.savebtn, 0, wx.ALIGN_RIGHT, 10)

		vbox.Add(pmrpathlabel, 0, wx.EXPAND | wx.TOP | wx.LEFT | wx.RIGHT, 10)
		vbox.Add((-1, 5))
		vbox.Add(self.pmrpathtc, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 10)
		vbox.Add((-1, 5))
		vbox.Add(pmrpathwarn, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 10)
		vbox.Add((-1, 25))
		vbox.Add(resolutionlbl, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 10)
		vbox.Add((-1, 5))		
		vbox.Add(hbox, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 10)
		vbox.Add((-1, 5))
		vbox.Add(resolutioninfo, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 10)
		vbox.Add((-1, 25))
		vbox.Add(sc4pathlabel, 0, wx.EXPAND | wx.TOP | wx.LEFT | wx.RIGHT, 10)
		vbox.Add((-1, 5))
		vbox.Add(self.sc4pathtc, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 10)
		vbox.Add((-1, 5))
		vbox.Add(sc4pathinfo, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 10)
		vbox.Add((-1, 25))
		vbox.Add(hbox2, 0, wx.EXPAND | wx.ALL, 10)

		panel.SetSizer(vbox)
		panel.Fit()

		self.SetTitle("SimCity 4 Launch Settings")

	def PopulateCurrentSettings(self):
		config = ConfigParser.RawConfigParser()
		config.read(get_pmr_path("config.ini"))

		self.pmrpathtc.SetValue(config.get('launcher', 'path'))
		self.reswtc.SetValue(config.get('launcher', 'resw'))
		self.reshtc.SetValue(config.get('launcher', 'resh'))
		self.sc4pathtc.SetValue(config.get('launcher', 'sc4path'))

	def onCancel(self, event):
		self.Close(0)

	def onSave(self, event):
		global PMR_LAUNCHPATH
		global PMR_LAUNCHRESW
		global PMR_LAUNCHRESH
		global PMR_CUSTOMPATH

		config = ConfigParser.RawConfigParser()

		try:
			int(self.reswtc.GetValue())
		except ValueError:
			self.WarnError("The custom resolution width must be an integer between 1024 and 2048.", "Bad width setting")  
			return False

		try:
			int(self.reshtc.GetValue())
		except ValueError:
			self.WarnError("The custom resolution height must be an integer between 1024 and 2048.", "Bad width setting")  
			return False

		pmrpath = self.pmrpathtc.GetValue()
		resw = int(self.reswtc.GetValue())
		resh = int(self.reshtc.GetValue())

		if not pmrpath:
			self.WarnError("Please enter a valid launch path.", "Bad launch path setting")  
			return False
		if not 1024 <= resw <= 2048:
			self.WarnError("The custom resolution width must be an integer between 1024 and 2048.", "Bad width setting")  
			return False
		if not 600 <= resh <= 1200:
			self.WarnError("The custom resolution height must be an integer between 600 and 1200.", "Bad height setting")  
			return False

		config.add_section('launcher')
		config.set('launcher', 'path', self.pmrpathtc.GetValue())
		config.set('launcher', 'resw', self.reswtc.GetValue())
		config.set('launcher', 'resh', self.reshtc.GetValue())
		config.set('launcher', 'sc4path', self.sc4pathtc.GetValue())
		
		try:
			PMR_LAUNCHPATH = config.get('launcher', 'path')
			PMR_LAUNCHRESW = config.get('launcher', 'resw')
			PMR_LAUNCHRESH = config.get('launcher', 'resh')
			PMR_CUSTOMPATH = config.get('launcher', 'sc4path')
		except:
			pass

		with open(get_pmr_path("config.ini"), 'wb') as configfile:
			config.write(configfile)

		self.Close(1)

class PMRClientFirstRun(wx.Dialog):

	def __init__(self, parent):
		super(PMRClientFirstRun, self).__init__(parent, style=wx.CAPTION)
		self.InitUI()
		self.Fit()
		self.Centre()
		self.Show()

	def InitUI(self):
		panel = wx.Panel(self)
		panel.SetBackgroundColour('#6B4C75')
		
		vbox = wx.BoxSizer(wx.VERTICAL)

		helpimg = wx.StaticBitmap(panel, wx.ID_ANY, wx.Bitmap(get_pmr_path("firstrun.png"), wx.BITMAP_TYPE_ANY))
		closebtn = wx.Button(panel, label='Close')
		closebtn.Bind(wx.EVT_BUTTON, self.onClose)

		vbox.Add(helpimg, 0, wx.EXPAND, 10)
		vbox.Add(closebtn, 0, wx.ALL | wx.ALIGN_RIGHT, 10)

		panel.SetSizer(vbox)
		panel.Fit()

		self.SetTitle("Welcome to PMR")

	def onClose(self, event = None):
		self.EndModal(1)


class PMRClientAuthenticator(wx.Dialog):

	def __init__(self, parent, selectedregion):
		super(PMRClientAuthenticator, self).__init__(parent, style= wx.SYSTEM_MENU | wx.CAPTION)
		self.Bind(EVT_AUTHENTICATIONRESPONSE, self.onAuthenticationResponse)

		self.region = selectedregion
		self.InitUI()
		self.Fit()
		self.Centre()
		self.Show()
		self.GetCredentials()

	def WarnError(parent, message, caption = 'Error!'):
		dlg = wx.MessageDialog(parent, message, caption, wx.OK | wx.ICON_ERROR)
		dlg.ShowModal()
		dlg.Destroy()

	def InitUI(self):
		panel = wx.Panel(self)
		panel.SetBackgroundColour('#eeeeee')
		
		vbox = wx.BoxSizer(wx.VERTICAL)

		self.infotext = wx.StaticText(panel, label='Log in with your PMR account to continue.', style=wx.ALIGN_CENTRE_HORIZONTAL|wx.ST_NO_AUTORESIZE)

		usernamelbl = wx.StaticText(panel, label='Username:')
		self.usernametc = wx.TextCtrl(panel)
		passwordlbl = wx.StaticText(panel, label='Password:')
		self.passwordtc = wx.TextCtrl(panel, style=wx.TE_PASSWORD)

		self.rememberpass = wx.CheckBox(panel, label='Remember me')
		self.rememberpass.Bind(wx.EVT_CHECKBOX, self.OnRememberToggle)

		hbox = wx.BoxSizer(wx.HORIZONTAL)
		accountlink = wx.HyperlinkCtrl(panel, label='Need an account?', url=PMR_SERVERPATH+'?ref=needaccount')
		self.cancelbtn = wx.Button(panel, label='Cancel')
		self.cancelbtn.Bind(wx.EVT_BUTTON, self.CancelAuthentication)
		self.loginbtn = wx.Button(panel, label='Log in')
		self.loginbtn.Bind(wx.EVT_BUTTON, self.AttemptAuthentication)
		self.loginbtn.SetFocus()
		hbox.Add(accountlink, 1, wx.ALIGN_LEFT | wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 10)
		hbox.Add(self.cancelbtn, 0, wx.RIGHT | wx.ALIGN_RIGHT, 5)
		hbox.Add(self.loginbtn, 0, wx.ALIGN_RIGHT, 10)

		vbox.Add(self.infotext, 0, wx.EXPAND | wx.ALL, 10)
		vbox.Add(usernamelbl, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 10)
		vbox.Add((-1, 5))
		vbox.Add(self.usernametc, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 10)
		vbox.Add((-1, 5))
		vbox.Add(passwordlbl, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 10)
		vbox.Add((-1, 5))
		vbox.Add(self.passwordtc, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 10)
		vbox.Add((-1, 10))
		vbox.Add(self.rememberpass, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)
		vbox.Add(hbox, 0, wx.EXPAND | wx.ALL, 10)

		panel.SetSizer(vbox)
		panel.Fit()

		self.SetTitle("Log in")

	def GetCredentials(self, event = None):
		saveduser = keyring.get_password("pmrsystem", "pmr-user")
		savedpass = keyring.get_password("pmrsystem", "pmr-pass")

		if saveduser and savedpass:
			saveduser = str(saveduser)
			savedpass = str(savedpass)
			self.usernametc.SetValue(saveduser)
			self.passwordtc.SetValue(savedpass)
			self.rememberpass.SetValue(True)

	def SetCredentials(self, event = None):
		keyring.set_password("pmrsystem", "pmr-user", self.usernametc.GetValue())
		keyring.set_password("pmrsystem", "pmr-pass", self.passwordtc.GetValue())

	def OnRememberToggle(self, event = None):
		if not (self.rememberpass.IsChecked()):
			keyring.set_password("pmrsystem", "pmr-user", "")
			keyring.set_password("pmrsystem", "pmr-pass", "")

	def CancelAuthentication(self, event = None):
		self.EndModal(0)

	def AttemptAuthentication(self, event = None):
		self.usernametc.Disable()
		self.passwordtc.Disable()
		self.rememberpass.Disable()
		self.loginbtn.Disable()

		if (self.rememberpass.IsChecked()):
			self.SetCredentials()
		
		userv = self.usernametc.GetValue()
		passv = self.passwordtc.GetValue()

		worker = AuthenticationRequestThread(self, userv, passv, self.region["id"])
		worker.setDaemon(True)
		worker.start()


	def onAuthenticationResponse(self, event):
		#resp = s.post(PMR_SERVERPATH + "authLogIn.php", data = {"username": userv, "password": passv, "region_id": self.region['id']})

		status_code = event.GetStatus()

		if status_code == 200:
			self.Authenticate()
		elif status_code == 401:
			self.WarnError("Sorry, but your username or password is incorrect. Please try again.", "Login failed")
		elif status_code == 403:
			self.WarnError("Sorry, but you are not allowed to access this region.", "Login failed")
		else:
			self.WarnError("Sorry, but PMR could not process this authentication request. Please try again.")

		self.usernametc.Enable()
		self.passwordtc.Enable()
		self.rememberpass.Enable()
		self.loginbtn.Enable()

	def Authenticate(self, event = None):
		self.EndModal(1)



class PMRClientRegionDownloader(wx.Dialog):

	def __init__(self, parent, selectedregion, refresher = False):
		super(PMRClientRegionDownloader, self).__init__(parent, style= wx.SYSTEM_MENU | wx.CAPTION)
		self.region = selectedregion;
		self.regiondir = os.path.join(PMR_LAUNCHPATH,"Regions",self.region["name"])
		self.refresher = refresher
		self.InitUI()
		self.Fit()
		self.Centre()
		self.Show()
		self.Bind(EVT_CITYLISTRESPONSE, self.DownloadRegion)
		self.Bind(EVT_PROGUPDATE, self.OnProgUpdate)
		#self.Bind(EVT_CONFIGBMPRESPONSE, self.MakeConfigFile)
		self.Bind(EVT_CONFIGBMPRESPONSE, self.DownloadPlugins)
		self.Bind(EVT_PLUGINSRESPONSE, self.onPluginsDownloaded)
		self.GetCityList()

	def WarnError(parent, message, caption = 'Error!'):
		dlg = wx.MessageDialog(parent, message, caption, wx.OK | wx.ICON_ERROR)
		dlg.ShowModal()
		dlg.Destroy()

	def InitUI(self):
		panel = wx.Panel(self)
		panel.SetBackgroundColour('#eeeeee')
		
		vbox = wx.BoxSizer(wx.VERTICAL)

		self.infotext = wx.StaticText(panel, label='Connecting to region...', style=wx.ST_NO_AUTORESIZE)

		self.progbar = wx.Gauge(panel, size=(300, 20))
		self.progbar.Pulse()

		self.cancelbtn = wx.Button(panel, label='Cancel')
		self.cancelbtn.Bind(wx.EVT_BUTTON, self.CancelDownload)

		vbox.Add(self.infotext, 0, wx.EXPAND | wx.ALL, 10)
		vbox.Add(self.progbar, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 10)
		vbox.Add(self.cancelbtn, 0, wx.ALIGN_RIGHT | wx.ALL, 10)

		panel.SetSizer(vbox)
		panel.Fit()

		self.SetTitle("Connecting to region...")

	def GetCityList(self, event = None):
		worker = CityListRequestThread(self, self.region["id"])
		worker.setDaemon(True)
		worker.start()

	def DownloadRegion(self, event = None):
		self.citylist = event.GetValue()

		self.infotext.SetLabel("Synchronizing cities...")

		self.progbar.SetValue(0)
		self.progbar.SetRange(len(self.citylist))

		regionsdirectory = os.path.join(PMR_LAUNCHPATH,"Regions")

		if not os.path.exists(regionsdirectory):
			os.makedirs(regionsdirectory)

		for the_file in os.listdir(regionsdirectory):
			file_path = os.path.join(regionsdirectory, the_file)
			try:
				if os.path.isfile(file_path):
					os.unlink(file_path)
				else:
					shutil.rmtree(file_path)
			except Exception as e:
				print(e)

		directory = os.path.join(PMR_LAUNCHPATH,"Regions",self.region["name"])

		if not os.path.isdir(directory):
			os.makedirs(directory)
		else:
			for the_file in os.listdir(directory):
				file_path = os.path.join(directory, the_file)
				try:
					if os.path.isfile(file_path):
						os.unlink(file_path)
				except Exception as e:
					print(e)

		for city in self.citylist:

			destination = os.path.join(directory, str(city["lastsaveid"]).zfill(8) + ".sc4")

			worker = BigDownloadThread(self, PMR_SERVERPATH+"getSave.php?city_id=" + str(city["id"]), destination, city["lastsaveid"], city["lastsavehash"])
			worker.setDaemon(True)
			worker.start()

	def OnProgUpdate(self, event = None):
		self.progbar.Value += 1
		if self.progbar.Value == len(self.citylist):
			self.DownloadConfigBmp()

	def DownloadConfigBmp(self, event = None):
		self.infotext.SetLabel("Preparing region...")
		self.progbar.Pulse()

		destination = os.path.join(self.regiondir,"config.bmp")
		worker = ConfigBmpRequestThread(self, self.region["id"], destination)
		worker.setDaemon(True)
		worker.start()

	def DownloadPlugins(self, event = None):
		if self.refresher:
			self.MakeConfigFile()
			return True

		self.infotext.SetLabel("Synchronizing plugins...")

		regionid = self.region["id"]
		destination = os.path.join(PMR_LAUNCHPATH,"Plugins","PMRPlugins",str(regionid).zfill(8) + ".zip")
		self.pluginszip = str(destination)

		worker = PluginsDownloadThread(self, regionid, destination)
		worker.setDaemon(True)
		worker.start()

	def onPluginsDownloaded(self, event):
		plugins = zipfile.ZipFile(self.pluginszip)
		plugins.extractall(os.path.join(PMR_LAUNCHPATH,"Plugins","PMRPlugins"))
		self.MakeConfigFile()

	def MakeConfigFile(self, event = None):
		Config = ConfigParser.ConfigParser()
		cfgfile = open(os.path.join(self.regiondir,"region.ini"),'w')
		cfgfile.write("; Generated by PMR Client 1.0.0\n")
		Config.add_section("Regional Settings")
		Config.set("Regional Settings", "Name", "[PMR] " + self.region["name"])
		Config.set("Regional Settings", "Terrain type", 0)
		Config.set("Regional Settings", "Water Min", 60)
		Config.set("Regional Settings", "Water Max", 100)
		Config.write(cfgfile)
		cfgfile.close()

		if self.refresher:
			self.DownloadSucceeded()

		AuxConfig = ConfigParser.ConfigParser()
		refreshregiondir = os.path.join(PMR_LAUNCHPATH,"Regions","ZZZRefreshAuxiliary")
		if not os.path.exists(refreshregiondir):
			os.makedirs(refreshregiondir)
		cfgfile = open(os.path.join(refreshregiondir,"region.ini"),'w')
		cfgfile.write("; Generated by PMR Client 1.0.0\n")
		AuxConfig.add_section("Regional Settings")
		AuxConfig.set("Regional Settings", "Name", "Load this region to refresh '" + self.region['name'] + "'")
		AuxConfig.set("Regional Settings", "Terrain type", 0)
		AuxConfig.set("Regional Settings", "Water Min", 60)
		AuxConfig.set("Regional Settings", "Water Max", 100)
		AuxConfig.write(cfgfile)
		cfgfile.close()
		shutil.copyfile(get_pmr_path("syncnotice.sc4"), os.path.join(refreshregiondir, "syncnotice.sc4"))
		shutil.copyfile(get_pmr_path("syncnotice.bmp"), os.path.join(refreshregiondir, "config.bmp"))

		self.DownloadSucceeded()

	def CancelDownload(self, event = None):
		self.EndModal(0)

	def DownloadFailed(self, event = None):
		self.EndModal(-1)

	def DownloadSucceeded(self, event = None):
		self.EndModal(1)




class PMRClientRegionInspector(wx.Frame):

	def __init__(self, parent, selectedregion):
		super(PMRClientRegionInspector, self).__init__(parent, style=wx.SYSTEM_MENU | wx.CAPTION)
		self.Bind(EVT_PONG, self.onPong)
		self.Bind(EVT_MAPDATARECEIVED, self.onMapDataReceived)
		self.Bind(EVT_PUSHCHANGESSTARTED, self.onPushChangesStarted)
		self.Bind(EVT_PUSHCHANGESFAILED, self.onPushChangesFailed)
		self.Bind(EVT_PUSHCHANGESSUCCEEDED, self.onPushChangesSucceeded)
		self.region = selectedregion
		self.tssuccess = wx.TextAttr(wx.GREEN)
		self.tserror = wx.TextAttr(wx.RED)

		self.InitUI()
		self.Fit()
		self.Show()
		self.MoveTopRight()

		self._badmapreqs = 0
		self._pushfails = 0

	def WarnError(parent, message, caption = 'Error!'):
		dlg = wx.MessageDialog(parent, message, caption, wx.OK | wx.ICON_ERROR)
		dlg.ShowModal()
		dlg.Destroy()

	def InitUI(self):
		panel = wx.Panel(self)
		panel.SetBackgroundColour('#eeeeee')
		
		ico = wx.Icon(get_pmr_path('icon.ico'), wx.BITMAP_TYPE_ICO)
		self.SetIcon(ico)

		vbox = wx.BoxSizer(wx.VERTICAL)

		# maptitletext = wx.StaticText(panel, label="Region Map")
		# f = maptitletext.GetFont() 
		# f.SetWeight(wx.BOLD) 
		# maptitletext.SetFont(f) 

		req = s.get(PMR_SERVERPATH+"showRegionMap.php?region_id=" + str(self.region["id"]), stream=True)
		mapimgdat = wx.ImageFromStream(StringIO.StringIO(req.content)).ConvertToBitmap()
		self.mapimgctrl = wx.StaticBitmap(panel, -1, mapimgdat)

		hbox = wx.BoxSizer(wx.HORIZONTAL)
		self.resyncbtn = wx.Button(panel, label="Refresh Region")
		self.resyncbtn.Bind(wx.EVT_BUTTON, self.onResyncStart)
		self.disconnectbtn = wx.Button(panel, label="Disconnect")
		self.disconnectbtn.Bind(wx.EVT_BUTTON, self.onDisconnect)
		hbox.InsertStretchSpacer(0)
		hbox.Add(self.resyncbtn, 0, wx.RIGHT | wx.ALIGN_RIGHT, 5)
		hbox.Add(self.disconnectbtn, 0, wx.ALIGN_RIGHT, 10)

		# vbox.Add(maptitletext, 0, wx.ALL, 10)
		vbox.Add(self.mapimgctrl, 0, wx.ALL | wx.EXPAND, 0)
		vbox.Add(hbox, 0, wx.EXPAND | wx.ALL, 10)

		panel.SetSizer(vbox)
		panel.Fit()

		self.SetTitle("Connected to region '" + self.region['name'] + "'")

		self.pingworker = PingThread(self)
		self.pingworker.setDaemon(True)
		self.pingworker.start()

		self.mapworker = GetMapLoopThread(self, self.region["id"])
		self.mapworker.setDaemon(True)
		self.mapworker.start()

		directory = os.path.join(PMR_LAUNCHPATH,"Regions",self.region["name"])
		self.watchchangesworker = WatchForChangesThread(self, directory)
		self.watchchangesworker.setDaemon(True)
		self.watchchangesworker.start()

		self.pushchangesworker = PushChangesThread(self)
		self.pushchangesworker.setDaemon(True)
		self.pushchangesworker.start()

	def MoveTopRight(self):
		dw, dh = wx.DisplaySize()
		w, h = self.GetSize()
		x = dw - w - 30
		y = 30
		self.SetPosition((x, y))

	def MakeImportant(self):
		self.Iconize(False)
		self.Raise()
		self.RequestUserAttention()

	def onPong(self, event):
		if event.GetStatus() == 200:
			return True
		elif event.GetStatus() == 401:
			self.onLostConnection()
		else:
			self.WarnError("bad server")
		self.MakeImportant()

	def onMapDataReceived(self, event):
		try:
			self.mapimgctrl.SetBitmap(event.GetMapData())
			self._badmapreqs = 0
		except:
			self._badmapreqs += 1
			print(self._badmapreqs)

			if self._badmapreqs > 5:
				self.mapimgctrl.SetBitmap(wx.Bitmap(get_pmr_path("nomap.png"), wx.BITMAP_TYPE_ANY))
				#self.statustext.SetLabel("Couldn't get region map. Retrying in 5 seconds...")


		self.Fit()
		self.Layout()
		self.Refresh()

	def onResyncStart(self, event):
		resyncdialog = PMRClientResync(None, self.region, self.watchchangesworker)
		resyncdialog.ShowModal()
		resyncdialog.Destroy()

	def onDisconnect(self, event = None):
		self.resyncbtn.Disable()
		self.disconnectbtn.Disable()
		try:
			r = s.get(PMR_SERVERPATH+"authLogOut.php")
		except:
			pass
		self.pingworker.abort()
		self.mapworker.abort()
		self.watchchangesworker.abort()
		self.pushchangesworker.abort()
		PMRClient(None)
		self.Close()

	def onLostConnection(self, event = None):
		self.Centre()
		self.disconnectbtn.Disable()
		self.pingworker.abort()
		self.WarnError("Your region session has expired.\n\nDue to connection issues, you were logged out of this region.\nPlease log in again to save your changes and continue playing on this region.\n\nIf you choose to not log in again, your unsaved changes will be lost.", "Disconnected from region")

		authdialog = PMRClientAuthenticator(None, self.region)
		authresult = authdialog.ShowModal()
		authdialog.Destroy()

		if authresult == 1:
			self.pingworker.resume()
			self.MoveTopRight()
			self.disconnectbtn.Enable()

	def onPushChangesStarted(self, event):
		self.resyncbtn.Disable()
		self.resyncbtn.SetLabel("Pushing saves...")
		self.disconnectbtn.Disable()

	def onPushChangesFailed(self, event):
		self.Centre()
		#self.disconnectbtn.Disable()
		#self.pingworker.abort()

		code = event.GetCode()

		if code == 9:
			self.WarnError("This is an occupied tile, so your claim was rejected by PMR\n\nYou can only claim unoccupied tiles, which are colored blue in the Launcher Map.")
			self.pushchangesworker.FlushSaves()
		elif code == 10:
			self.WarnError("You already have a claim, so your last save was rejected by PMR\n\nYou can only make changes to your claim, and you can only have one claim per region.\n\nYour claim is the green tile in the Launcher Map.")
			self.pushchangesworker.FlushSaves()
		else:
			self._pushfails += 1

			if self._pushfails > 5:
				#self.pushchangesworker.SalvageSaves()
				self.WarnError("Sorry, but your last save could not be recognized by PMR\n\nTo ensure that your save won't be lost, we have moved it to the 'PMRSalvage' directory.\n\nPlease consult the manual for more information.")
				for i,save in enumerate(stagedsaves):
					shutil.copyfile(save["path"], os.path.join(PMR_LAUNCHPATH, "PMRSalvage", os.path.basename(os.path.normpath(save["path"]))))
				self._pushfails = 0
				self.pushchangesworker.FlushSaves()

		self.MoveTopRight()
		self.resyncbtn.Enable()
		self.resyncbtn.SetLabel("Refresh Region")
		self.disconnectbtn.Enable()

		#self.WarnError(str(event.GetCode()))

	def onPushChangesSucceeded(self, event):
		self.resyncbtn.SetLabel("Refresh Region")
		self.resyncbtn.Enable()
		self.disconnectbtn.Enable()
		self.mapworker.run(False)

class PMRClientResync(wx.Dialog):
	def __init__(self, parent,selectedregion, watchchangesworker):
		super(PMRClientResync, self).__init__(parent, style=wx.CAPTION)
		self.selectedregion = selectedregion
		self.watchchangesworker = watchchangesworker

		self.InitUI()
		self.Fit()
		self.Centre()
		self.Show()

	def InitUI(self):
		panel = wx.Panel(self)
		panel.SetBackgroundColour('#eeeeee')
		
		vbox = wx.BoxSizer(wx.VERTICAL)

		self.helptext = wx.StaticText(panel, label="The PMR Launcher automatically pushes your saves, but you must manually refresh the region to see others' changes.\n\nFirst, load the region that is titled 'Load this region to refresh...'")
		self.helptext.Wrap(390)

		self.helpimg = wx.StaticBitmap(panel, wx.ID_ANY, wx.Bitmap(get_pmr_path("sync1.png"), wx.BITMAP_TYPE_ANY))

		hbox = wx.BoxSizer(wx.HORIZONTAL)
		self.cancelbtn = wx.Button(panel, label='Cancel')
		self.cancelbtn.Bind(wx.EVT_BUTTON, self.onClose)
		self.contbtn = wx.Button(panel, label='Refresh Region')
		self.contbtn.Bind(wx.EVT_BUTTON, self.onCont)
		self.contbtn.SetFocus()
		hbox.InsertStretchSpacer(0)
		hbox.Add(self.cancelbtn, 0, wx.RIGHT | wx.ALIGN_RIGHT, 5)
		hbox.Add(self.contbtn, 0, wx.ALIGN_RIGHT, 10)

		vbox.Add(self.helpimg, 0, wx.ALL | wx.EXPAND, 10)
		vbox.Add(self.helptext, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)
		vbox.Add(hbox, 1, wx.ALL | wx.ALIGN_RIGHT, 10)

		panel.SetSizer(vbox)
		panel.Fit()

		self.SetTitle("Refresh Region")

	def onCont(self, event = None):
		self.cancelbtn.Disable()
		self.contbtn.Disable()

		self.watchchangesworker.abort()

		downloaddialog = PMRClientRegionDownloader(None,self.selectedregion,True)
		downloadresult = downloaddialog.ShowModal()
		downloaddialog.Destroy()

		self.watchchangesworker.resume()

		self.helpimg.SetBitmap(wx.Bitmap(get_pmr_path("sync2.png"), wx.BITMAP_TYPE_ANY))
		self.helptext.SetLabel("The region has been refreshed successfully. You may now load the main region and see what's new.")
		self.helptext.Wrap(390)

		self.cancelbtn.Destroy()
		self.contbtn.SetLabel("Done")
		self.contbtn.Bind(wx.EVT_BUTTON, self.onClose)
		self.contbtn.Enable()

	def onClose(self, event):
		self.EndModal(0)

myEVT_LISTINGRESPONSE = wx.NewEventType()
EVT_LISTINGRESPONSE = wx.PyEventBinder(myEVT_LISTINGRESPONSE, 1)
class ListingResponseEvent(wx.PyCommandEvent):
	def __init__(self, etype, eid, value=None):
		wx.PyCommandEvent.__init__(self, etype, eid)
		self._value = value

	def GetValue(self):
		return self._value



class ListingRequestThread(threading.Thread):
	def __init__(self, parent):
		threading.Thread.__init__(self)
		self._parent = parent

	def run(self):
		response = s.get(PMR_SERVERPATH+"getRegionListing.php")
		listings = response.json()
		evt = ListingResponseEvent(myEVT_LISTINGRESPONSE, -1, listings)
		wx.PostEvent(self._parent, evt)



myEVT_SERVERSTATUSRESPONSE = wx.NewEventType()
EVT_SERVERSTATUSRESPONSE = wx.PyEventBinder(myEVT_SERVERSTATUSRESPONSE, 1)
class ServerStatusResponseEvent(wx.PyCommandEvent):
	def __init__(self, etype, eid, notices=None):
		wx.PyCommandEvent.__init__(self, etype, eid)
		self._notices = notices

	def GetNotices(self):
		return self._notices
class ServerStatusRequestThread(threading.Thread):
	def __init__(self, parent):
		threading.Thread.__init__(self)
		self._parent = parent

	def run(self):
		r = s.get(PMR_SERVERPATH+"getServerStatus.php")
		notices = r.json()
		evt = ServerStatusResponseEvent(myEVT_SERVERSTATUSRESPONSE, -1, notices)
		wx.PostEvent(self._parent, evt)



myEVT_AUTHENTICATIONRESPONSE = wx.NewEventType()
EVT_AUTHENTICATIONRESPONSE = wx.PyEventBinder(myEVT_AUTHENTICATIONRESPONSE, 1)
class AuthenticationResponseEvent(wx.PyCommandEvent):
	def __init__(self, etype, eid, status):
		wx.PyCommandEvent.__init__(self, etype, eid)
		self._status = status
	def GetStatus(self):
		return self._status
class AuthenticationRequestThread(threading.Thread):
	def __init__(self, parent, username, password, regionid):
		threading.Thread.__init__(self)
		self._parent = parent
		self._username = username
		self._password = password
		self._regionid = regionid

	def run(self):
		resp = s.post(PMR_SERVERPATH + "authLogIn.php", data = {"username": self._username, "password": self._password, "region_id": self._regionid})

		evt = AuthenticationResponseEvent(myEVT_AUTHENTICATIONRESPONSE, -1, resp.status_code)
		wx.PostEvent(self._parent, evt)



myEVT_CITYLISTRESPONSE = wx.NewEventType()
EVT_CITYLISTRESPONSE = wx.PyEventBinder(myEVT_CITYLISTRESPONSE, 1)
class CityListResponseEvent(wx.PyCommandEvent):
	def __init__(self, etype, eid, value=None):
		wx.PyCommandEvent.__init__(self, etype, eid)
		self._value = value

	def GetValue(self):
		return self._value



class CityListRequestThread(threading.Thread):
	def __init__(self, parent, regionid):
		threading.Thread.__init__(self)
		self._parent = parent
		self._regionid = regionid

	def run(self):
		response = requests.get(PMR_SERVERPATH+"getRegionCities.php?region_id=" + str(self._regionid))
		citylist = response.json()
		evt = CityListResponseEvent(myEVT_CITYLISTRESPONSE, -1, citylist)
		wx.PostEvent(self._parent, evt)



myEVT_PROGUPDATE = wx.NewEventType()
EVT_PROGUPDATE = wx.PyEventBinder(myEVT_PROGUPDATE, 1)
class ProgUpdateEvent(wx.PyCommandEvent):
	def __init__(self, etype, eid, value=None):
		wx.PyCommandEvent.__init__(self, etype, eid)
		self._value = value

	def GetValue(self):
		return self._value



class BigDownloadThread(threading.Thread):
	def __init__(self, parent, url, destination, saveid, savehash):
		threading.Thread.__init__(self)
		self._parent = parent
		self._url = url
		self._destination = destination
		self._saveid = saveid
		self._savehash = savehash

	def run(self):
		cachedsavepath = os.path.join(PMR_LAUNCHPATH,"PMRCache",str(self._saveid).zfill(8) + ".sc4")

		print("### PATH")
		print(os.path.exists(cachedsavepath))
		print("### HASH")
		#print(md5(cachedsavepath) == self._savehash)

		if os.path.exists(cachedsavepath) and md5(cachedsavepath) == self._savehash:
			shutil.copyfile(cachedsavepath, self._destination)
			print("cached version okay!")
		else:
			print("using downloaded version!")
			response = requests.get(self._url, stream=True)
			handle = open(str(self._destination), "wb")
			for chunk in response.iter_content(chunk_size=512):
				if chunk:
					handle.write(chunk)
			handle.close()

			shutil.copyfile(self._destination, cachedsavepath)

		evt = ProgUpdateEvent(myEVT_PROGUPDATE, -1, 1)
		wx.PostEvent(self._parent, evt)


myEVT_PLUGINSRESPONSE = wx.NewEventType()
EVT_PLUGINSRESPONSE = wx.PyEventBinder(myEVT_PLUGINSRESPONSE, 1)
class PluginsResponseEvent(wx.PyCommandEvent):
	def __init__(self, etype, eid, value=None):
		wx.PyCommandEvent.__init__(self, etype, eid)
		self._value = value

	def GetValue(self):
		return self._value
class PluginsDownloadThread(threading.Thread):
	def __init__(self, parent, regionid, destination):
		threading.Thread.__init__(self)
		self._parent = parent
		self._regionid = regionid
		self._destination = destination

	def run(self):
		cachedpluginspath = os.path.join(PMR_LAUNCHPATH,"PMRPluginsCache",str(self._regionid).zfill(8) + ".zip")
		hashreq = s.get(PMR_SERVERPATH+"getPluginsHash.php?region_id="+str(self._regionid))
		pluginshash = hashreq.text
		url = PMR_SERVERPATH+"getPlugins.php?region_id="+str(self._regionid)


		if os.path.exists(cachedpluginspath) and md5(cachedpluginspath) == pluginshash:
			shutil.copyfile(cachedpluginspath, self._destination)
			print("[PLUGINS] cached version okay!")
		else:
			print("[PLUGINS] using downloaded version!")
			response = requests.get(url, stream=True)
			handle = open(str(self._destination), "wb")
			for chunk in response.iter_content(chunk_size=512):
				if chunk:
					handle.write(chunk)
			handle.close()

			shutil.copyfile(self._destination, cachedpluginspath)

		evt = PluginsResponseEvent(myEVT_PLUGINSRESPONSE, -1, 1)
		wx.PostEvent(self._parent, evt)


myEVT_CONFIGBMPRESPONSE = wx.NewEventType()
EVT_CONFIGBMPRESPONSE = wx.PyEventBinder(myEVT_CONFIGBMPRESPONSE, 1)
class ConfigBmpResponseEvent(wx.PyCommandEvent):
	def __init__(self, etype, eid, value=None):
		wx.PyCommandEvent.__init__(self, etype, eid)
		self._value = value

	def GetValue(self):
		return self._value
class ConfigBmpRequestThread(threading.Thread):
	def __init__(self, parent, regionid, destination):
		threading.Thread.__init__(self)
		self._parent = parent
		self._regionid = regionid
		self._destination = destination

	def run(self):
		response = requests.get(PMR_SERVERPATH+"getRegionConfig.php?region_id=" + str(self._regionid))
		with open(self._destination, 'wb') as f:
			f.write(response.content)
		evt = ConfigBmpResponseEvent(myEVT_CONFIGBMPRESPONSE, -1, 1)
		wx.PostEvent(self._parent, evt)



myEVT_PONG = wx.NewEventType()
EVT_PONG = wx.PyEventBinder(myEVT_PONG, 1)
class PongEvent(wx.PyCommandEvent):
	def __init__(self, etype, eid, status):
		wx.PyCommandEvent.__init__(self, etype, eid)
		self._status = status
	def GetStatus(self):
		return self._status



class PingThread(threading.Thread):
	def __init__(self, parent):
		threading.Thread.__init__(self)
		self._parent = parent
		self._runflag = True

	def run(self):
		while self._runflag:
			resp = s.get(PMR_SERVERPATH+"authPing.php")
			evt = PongEvent(myEVT_PONG, -1, resp.status_code)
			wx.PostEvent(self._parent, evt)
			time.sleep(2)

	def abort(self):
		self._runflag = False

	def resume(self):
		self._runflag = True

myEVT_MAPDATARECEIVED = wx.NewEventType()
EVT_MAPDATARECEIVED = wx.PyEventBinder(myEVT_MAPDATARECEIVED, 1)
class MapDataReceivedEvent(wx.PyCommandEvent):
	def __init__(self, etype, eid, data):
		wx.PyCommandEvent.__init__(self, etype, eid)
		self._data = data
	def GetMapData(self):
		return self._data

class GetMapLoopThread(threading.Thread):
	def __init__(self, parent, regionid):
		threading.Thread.__init__(self)
		self._parent = parent
		self._regionid = regionid
		self._runflag = True

	def run(self, doloop = True):
		while self._runflag:
			try:
				req = s.get(PMR_SERVERPATH+"showRegionMap.php?region_id=" + str(self._regionid), stream=True)
				req.raise_for_status()
			#except requests.exceptions.HTTPError as err:
			except:
				mapimgdat = -1
			else:
				mapimgdat = wx.ImageFromStream(StringIO.StringIO(req.content)).ConvertToBitmap()

			if self._runflag:
				evt = MapDataReceivedEvent(myEVT_MAPDATARECEIVED, -1, mapimgdat)
				wx.PostEvent(self._parent, evt)
			
			if not doloop:
				break
			else:
				time.sleep(5)

	def abort(self):
		self._runflag = False

myEVT_PUSHCHANGESSTARTED = wx.NewEventType()
EVT_PUSHCHANGESSTARTED = wx.PyEventBinder(myEVT_PUSHCHANGESSTARTED, 1)
class PushChangesStartedEvent(wx.PyCommandEvent):
	def __init__(self, etype, eid):
		wx.PyCommandEvent.__init__(self, etype, eid)

myEVT_PUSHCHANGESFAILED = wx.NewEventType()
EVT_PUSHCHANGESFAILED = wx.PyEventBinder(myEVT_PUSHCHANGESFAILED, 1)
class PushChangesFailedEvent(wx.PyCommandEvent):
	def __init__(self, etype, eid, code):
		wx.PyCommandEvent.__init__(self, etype, eid)
		self._code = code
	def GetCode(self):
		return self._code

myEVT_PUSHCHANGESSUCCEEDED = wx.NewEventType()
EVT_PUSHCHANGESSUCCEEDED = wx.PyEventBinder(myEVT_PUSHCHANGESSUCCEEDED, 1)
class PushChangesSucceededEvent(wx.PyCommandEvent):
	def __init__(self, etype, eid):
		wx.PyCommandEvent.__init__(self, etype, eid)

class WatchForChangesThread(threading.Thread):
	def __init__(self, parent, directory):
		threading.Thread.__init__(self)
		self._parent = parent
		self._directory = directory
		self._runflag = True

	def run(self):
		self.observer = Observer()
		self.eventhandler = WatchForChangesEventHandler()
		self.observer.schedule(self.eventhandler, self._directory, recursive=True)
		self.observer.start()

		# if self._runflag:
		# 	time.sleep(5)
		# 	self.run()
		# else:
		# 	self.observer.stop()

		try:
			while True:
				#print("looking")
				time.sleep(1)
		except:
			self.observer.stop()
			print "ERROR"

		self.observer.join()

	def abort(self):
		self._runflag = False
		self.observer.unschedule_all()

	def resume(self):
		self._runflag = True
		self.observer.schedule(self.eventhandler, self._directory, recursive=True)

class WatchForChangesEventHandler(FileSystemEventHandler):
	@staticmethod
	def on_any_event(event):
		if event.is_directory:
			return None
		elif event.event_type == 'created':
			# Take any action here when a file is first created.
			#print "Received created event - %s." % event.src_path
			for i, save in enumerate(stagedsaves):
				if save["path"] == event.src_path:
					return False
			e = {"path": event.src_path, "time": time.time()}
			stagedsaves.append(dict(e))
		elif event.event_type == 'modified':
			# Taken any action here when a file is modified.
			#print "Received modified event - %s." % event.src_path
			for i, save in enumerate(stagedsaves):
				if save["path"] == event.src_path:
					return False
			e = {"path": event.src_path, "time": time.time()}
			stagedsaves.append(dict(e))
		print stagedsaves

class PushChangesThread(threading.Thread):
	def __init__(self, parent):
		threading.Thread.__init__(self)
		self._parent = parent
		self._runflag = True

	def run(self):
		global stagedsaves
		mostrecent = 0

		while self._runflag == True:
			time.sleep(1)

			print("looking to push")

			for i, save in enumerate(stagedsaves):
				if save["time"] > mostrecent:
					mostrecent = save["time"]

				if time.time() - save["time"] > 100 or not save["path"].endswith(".sc4"):
					stagedsaves.pop(i)

			if time.time() - mostrecent > 2 and len(stagedsaves) > 2:
				sevt = PushChangesStartedEvent(myEVT_PUSHCHANGESSTARTED, -1)
				wx.PostEvent(self._parent, sevt)

				zfname = "temp" + str(time.time()) + ".zip"
				zf = zipfile.ZipFile(zfname, "w", zipfile.ZIP_DEFLATED)
				for i, save in enumerate(stagedsaves):
					dname = os.path.basename(os.path.normpath(save["path"]))
					if os.path.isfile(os.path.normpath(save["path"])):
						zf.write(save["path"], dname)
				zf.close()

				#files = {'save': open(zfname, 'rb')}

				try:
					#r = s.post(PMR_SERVERPATH+"pushChanges.php", files=files)
					
					with open(zfname, 'rb') as f:
						r = s.post(PMR_SERVERPATH+"pushChanges.php", files={'save': f})
						r.raise_for_status()
				except requests.exceptions.HTTPError as err:
					error = r.json()
					code = error["code"]

					print code
					evt = PushChangesFailedEvent(myEVT_PUSHCHANGESFAILED, -1, code)
					wx.PostEvent(self._parent, evt)

					pass;
				except:
					evt = PushChangesFailedEvent(myEVT_PUSHCHANGESFAILED, -1, -1)
					wx.PostEvent(self._parent, evt)
				else:
					evt = PushChangesSucceededEvent(myEVT_PUSHCHANGESSUCCEEDED, -1)
					wx.PostEvent(self._parent, evt)
					stagedsaves = []

				os.remove(zfname)	

	def abort(self):
		self._runflag = False

	def resume(self):
		self._runflag = True

	def FlushSaves(self):
		global stagedsaves
		stagedsaves = []

def main():
	pmr = wx.App()
	PMRClient(None)
	pmr.MainLoop()

if __name__ == '__main__':
	main()