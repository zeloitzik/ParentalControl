import win32security
import ctypes

def get_active_sid_ctypes():
    session_id = ctypes.windll.kernel32.WTSGetActiveConsoleSessionId()
    wtsapi32 = ctypes.windll.wtsapi32
    buffer = ctypes.c_wchar_p()
    bytes_returned = ctypes.c_uint()
    
    username = None
    domain = None
    
    if wtsapi32.WTSQuerySessionInformationW(0, session_id, 5, ctypes.byref(buffer), ctypes.byref(bytes_returned)):
        username = buffer.value
        wtsapi32.WTSFreeMemory(buffer)
        
    if wtsapi32.WTSQuerySessionInformationW(0, session_id, 7, ctypes.byref(buffer), ctypes.byref(bytes_returned)):
        domain = buffer.value
        wtsapi32.WTSFreeMemory(buffer)
        
    if username:
        user_str = f"{domain}\\{username}" if domain else username
        try:
            sid_obj, _, _ = win32security.LookupAccountName(None, user_str)
            return win32security.ConvertSidToStringSid(sid_obj)
        except Exception as e:
            return str(e)
    return "No username"

print("Ctypes:", get_active_sid_ctypes())
