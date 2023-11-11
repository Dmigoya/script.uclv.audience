import xbmc
import xbmcgui
import json
import requests
import os
from datetime import datetime
import shutil
import uuid

# globals
configPath = '/Users/davidmigoya/Library/Application Support/Kodi/addons/script.uclv.audience/config.json'


# View
def notification(tittle, message, time):
    dialog = xbmcgui.Dialog()
    dialog.notification(tittle, message, xbmcgui.NOTIFICATION_INFO, time)


def dialog(tittle, message):
    dialog = xbmcgui.Dialog()
    dialog.ok(tittle, message)


def dialogYesNoCopyFileDataToUSB(tittle, message, pathUSB):
    dialog = xbmcgui.Dialog()
    isPresedYes = dialog.yesno(tittle, message)
    if isPresedYes:
        copyDataFile(pathUSB)
        return True
    else:
        return False


def dialogYesNoRemovedFileData(tittle, message):
    dialog = xbmcgui.Dialog()
    isPresedYes = dialog.yesno(tittle, message)
    if isPresedYes:
        removeDataFile()
        return True
    else:
        return False

def dialogInput(tittle):
    d = xbmcgui.Dialog()
    return d.input(tittle)

# Data
def readConfigs():
    global configPath
    try:
        with open(configPath) as f:
            return json.load(f)
    except Exception as e:
        notification("Audiometer", f"Error al leer configuraciones: {e}", 5000)
        return {}



def writeData(data):
    if not isSpaceAvaiable():
        notification('Audiometer', 'No hay espacio en el disco', 10000)
        return
    configs = readConfigs()
    path = configs['master_path'] + configs['data_name_file']
    fileJson = readData()
    if fileJson != None and 'data' in fileJson:
        fileJson['data'].append(data)
    else:
        fileJson = {'data': []}
        fileJson['data'].append(data)

    with open(path, 'w') as f:
        json.dump(fileJson, f)


def readData():
    configs = readConfigs()
    path = configs['master_path'] + configs['data_name_file']
    try:
        with open(path) as f:
            return json.load(f)
    except FileNotFoundError:
        data = {}
        with open(path, 'w') as f:
            json.dump(data, f)
        return data


def getModelDataToSave(name, timeIn):
    data = {}
    data['name'] = name
    data['time_in'] = timeIn.strftime('%Y-%m-%dT%H:%M:%S.%f')
    data['time_out'] = datetime.now().strftime('%Y-%m-%dT%H:%M:%S.%f')
    return data


def removeDataFile():
    configs = readConfigs()
    path = configs['master_path'] + configs['data_name_file']
    if os.path.exists(path):
        os.remove(path)


def existDataFile():
    configs = readConfigs()
    path = configs['master_path'] + configs['data_name_file']
    return os.path.exists(path)


def copyDataFile(pathEnd):
    configs = readConfigs()
    pathIn = configs['master_path'] + configs['data_name_file']
    shutil.copy(pathIn, pathEnd)


def isSpaceAvaiable():
    configs = readConfigs()
    path = configs['master_path']
    dataFile = configs['data_name_file']
    if os.path.exists(path):
        statvfs = os.statvfs(path)
        freeSpace = statvfs.f_bavail * statvfs.f_frsize
        if os.path.exists(path + dataFile):
            sizeFile = os.path.getsize(path + dataFile)
            freeSpace = freeSpace - sizeFile
        if freeSpace > configs["max_space_kb"]:
            return True
        else:
            return False
    else:
        return False


def findUSB():
    folder_usb = "/media/" + os.getenv("USER")
    files = os.listdir(folder_usb)
    for file in files:
        path = folder_usb + "/" + file
        if os.path.ismount(path):
            return True, (path + "/"), file
    return False, '', ''


def getUUID():
    return str(uuid.getnode())


# API
def getTokenJWT():
    configs = readConfigs()
    urlbase = configs["url_api"] + ":" + configs["port_api"]
    url = urlbase + "/api/v1/login"

    payload = json.dumps({
        "userName": "dmigoya@uclv.cu",
        "password": "1234"
    })
    headers = {
        'Content-Type': 'application/json'
    }

    try:
        response = requests.request("POST", url, headers=headers, data=payload)
        if response.status_code == 200:
            return response.json()['token']
        else:
            notification("Audiometer", f"Error al obtener token JWT: {response.status_code}", 5000)
            return ''
    except Exception as e:
        notification("Audiometer", f"Error en la solicitud de JWT: {e}", 5000)
        return ''


def sendData():
    if not existDataFile():
        return True
    configs = readConfigs()
    baseUrl = configs["url_api"] + ":" + configs["port_api"]
    url = baseUrl + "/api/v1/data/saveData"
    payload = readData()
    token = getTokenJWT()
    if token == '':
        return False
    else:
        token = "Bearer " + token

    headers = {
        "Authorization": token,
        'Content-Type': 'application/json'}

    response = requests.post(url, data=json.dumps(payload), headers=headers)

    if response.status_code == 200:
        removeDataFile()
        return True
    else:
        return False


# test-------------------------------------------------------------------------

# main-------------------------------------------------------------------------
notification("Audiometer", "The addon is running", 5000)
configs = readConfigs()
timeIn = datetime.now()
flagSaveDone = True
name = ''


# logic
def copyToUSBLogic():
    if not existDataFile():
        return
    usbFinded, pathUSB, usbName = findUSB()
    if usbFinded:
        copied = dialogYesNoCopyFileDataToUSB("Audiometer", "Copiar los datos registrados en la USB " + usbName,
                                              pathUSB)
        if copied:
            deleted = dialogYesNoRemovedFileData("Audiometer", "Eliminar los datos ya copiados")
            if deleted:
                notification("Audiometer", "Datos copiados y eliminados", 5000)
            else:
                notification("Audiometer", "Datos copiados", 5000)


while True:
    if xbmc.Player().isPlaying():
        flagSaveDone = False
        if name == '':
            name = xbmc.getInfoLabel("Player.Title")
            timeIn = datetime.now()
            xbmc.sleep(1000 * configs["sleep_time"])
            continue
        if xbmc.getInfoLabel("Player.Title") != name:
            data = getModelDataToSave(name, timeIn)
            writeData(data)
            name = xbmc.getInfoLabel("Player.Title")
            timeIn = datetime.now()
            xbmc.sleep(1000 * configs["sleep_time"])
            continue
    else:
        if not flagSaveDone:
            data = getModelDataToSave(name, timeIn)
            writeData(data)
            name = ''
            flagSaveDone = True
            xbmc.sleep(1000 * configs["sleep_time"])
            continue
    pass

# duration = xbmc.getInfoLabel("Player.Time")
# videoFormat = xbmc.getInfoLabel("Player.VideoCodec")
# audioFormat = xbmc.getInfoLabel("Player.AudioCodec")
