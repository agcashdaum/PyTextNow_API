if __name__ == "__main__":
    from login import login
else:
    from pytextnow.login import login
    from pytextnow.error import FailedRequest, AuthError, InvalidEvent
    from pytextnow.message_container import MessageContainer
    from pytextnow.multi_media_message import MultiMediaMessage
    from pytextnow.message import Message
import mimetypes
import requests
from datetime import datetime, time
from dateutil.relativedelta import relativedelta

import json
from os.path import realpath, dirname, join
import time
import atexit

MESSAGE_TYPE = 0
MULTIMEDIA_MESSAGE_TYPE = 1

SENT_MESSAGE_TYPE = 2
RECEIVED_MESSAGE_TYPE = 1

SIP_ENDPOINT = "prod.tncp.textnow.com"


class Client:
    def __init__(self, username: str = None, cookie=None):
        # Load SIDS
        self._user_sid = {}
        self._good_parse = False
        self._user_sid_file = join(dirname(realpath(__file__)), 'user_sids.json')

        try:
            with open(self._user_sid_file, 'r') as file:
                self._user_sid = json.loads(file.read())
                self._good_parse = True
        except json.decoder.JSONDecodeError:
            with open(self._user_sid_file, 'w') as file:
                file.write('{}')

        self.username = username
        self.allowed_events = ["message"]

        self.events = []

        if self.username in self._user_sid.keys():
            sid = cookie if cookie else self._user_sid[self.username]
            self.cookies = {
                'connect.sid': sid
            }
            self._user_sid[self.username] = sid
            if cookie and not self._good_parse:
                with open(self._user_sid_file, "w") as file:
                    file.write(json.dumps(self._user_sid))
        else:
            sid = cookie if cookie else login()
            self.cookies = {
                'connect.sid': sid
            }
            self._user_sid[self.username] = sid
            with open(self._user_sid_file, "w") as file:
                file.write(json.dumps(self._user_sid))

        self.headers = {
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) '
                          'Chrome/88.0.4324.104 Safari/537.36 '
        }

        file.close()

        def on_exit():
            if len(self.events) == 0:
                return

            while 1:
                for event, func in self.events:
                    if event == "message":
                        unread_msgs = self.get_unread_messages()
                        for msg in unread_msgs:
                            msg.mark_as_read()
                            func(msg)

        atexit.register(on_exit)

    # Functions
    def auth_reset(self, cookie=None):
        with open(self._user_sid_file, "r") as user_SIDS_file:
            user_SIDS = json.loads(user_SIDS_file.read())

        if self.username in user_SIDS.keys():
            del user_SIDS[self.username]

            with open(self._user_sid_file, "w") as user_SIDS_file:
                user_SIDS_file.write(json.dumps(user_SIDS))

            self.__init__(self.username, cookie)
        else:
            if cookie:
                user_SIDS[self.username] = cookie
                with open(self._user_sid_file, "w") as user_SIDS_file:
                    user_SIDS_file.write(json.dumps(user_SIDS))
                self.__init__(self.username)
            else:
                raise AuthError("You haven't authenticated before.")

    def get_messages(self):
        """
            This gets most of the messages both sent and received. However It won't get all of them just the past 10-15
        """
        req = requests.get("https://www.textnow.com/api/users/" + self.username + "/messages", headers=self.headers,
                           cookies=self.cookies)
        if str(req.status_code).startswith("2"):
            messages = json.loads(req.content)
            messages = [
                Message(msg, self) if not msg["message"].startswith("http") else MultiMediaMessage(msg, self)
                for msg in messages["messages"]]
            return MessageContainer(messages, self)
        else:
            self.request_handler(req.status_code)

    def get_raw_messages(self):
        """
            This gets most of the messages both sent and received. However It won't get all of them just the past 10-15
        """
        req = requests.get("https://www.textnow.com/api/users/" + self.username + "/messages", headers=self.headers,
                           cookies=self.cookies)
        if str(req.status_code).startswith("2"):
            messages = json.loads(req.content)
            return messages["messages"]
        else:
            self.request_handler(req.status_code)

    def get_sent_messages(self):
        """
            This gets all the past 10-15 messages sent by your account
        """
        sent_messages = self.get_messages()
        sent_messages = [msg for msg in sent_messages if msg.direction == SENT_MESSAGE_TYPE]

        return MessageContainer(sent_messages, self)

    def get_received_messages(self):
        """
            Gets inbound messages
        """
        messages = self.get_messages()
        messages = [msg for msg in messages if msg.direction == RECEIVED_MESSAGE_TYPE]

        return MessageContainer(messages, self)

    def get_unread_messages(self):
        """
            Gets unread messages
        """
        new_messages = self.get_received_messages()
        new_messages = [msg for msg in new_messages if not msg.read]

        return MessageContainer(new_messages, self)

    def get_read_messages(self):
        """
            Gets read messages
        """
        new_messages = self.get_received_messages()
        new_messages = [msg for msg in new_messages if msg.read]

        return MessageContainer(new_messages, self)

    def send_mms(self, to, file):
        """
            This function sends a file/media to the number
        """
        mime_type = mimetypes.guess_type(file)[0]
        file_type = mime_type.split("/")[0]
        has_video = True if file_type == "video" else False
        msg_type = 2 if file_type == "image" else 4

        file_url_holder_req = requests.get("https://www.textnow.com/api/v3/attachment_url?message_type=2",
                                           cookies=self.cookies, headers=self.headers)
        if str(file_url_holder_req.status_code).startswith("2"):
            file_url_holder = json.loads(file_url_holder_req.text)["result"]

            with open(file, mode="rb") as f:
                raw = f.read()

                headers_place_file = {
                    'accept': '*/*',
                    'content-type': mime_type,
                    'accept-language': 'en-US,en;q=0.9',
                    "mode": "cors",
                    "method": "PUT",
                    "credentials": 'omit'
                }

                place_file_req = requests.put(file_url_holder, data=raw, headers=headers_place_file,
                                              cookies=self.cookies)
                if str(place_file_req.status_code).startswith("2"):

                    json_data = {
                        "contact_value": to,
                        "contact_type": 2, "read": 1,
                        "message_direction": 2, "message_type": msg_type,
                        "from_name": self.username,
                        "has_video": has_video,
                        "new": True,
                        "date": datetime.now().isoformat(),
                        "attachment_url": file_url_holder,
                        "media_type": file_type
                    }

                    send_file_req = requests.post("https://www.textnow.com/api/v3/send_attachment", data=json_data,
                                                  headers=self.headers, cookies=self.cookies)
                    return send_file_req
                else:
                    self.request_handler(place_file_req.status_code)
        else:
            self.request_handler(file_url_holder_req.status_code)

    def send_sms(self, to, text):
        """
            Sends an sms text message to this number
        """
        data = \
            {
                'json': '{"contact_value":"' + to + '","contact_type":2,"message":"' + text + '","read":1,'
                                                                                              '"message_direction":2,'
                                                                                              '"message_type":1,'
                                                                                              '"from_name":"' +
                        self.username + '","has_video":false,"new":true,"date":"' + datetime.now().isoformat() + '"} '
            }

        response = requests.post('https://www.textnow.com/api/users/' + self.username + '/messages',
                                 headers=self.headers, cookies=self.cookies, data=data)
        if not str(response.status_code).startswith("2"):
            self.request_handler(response.status_code)
        return response

    def wait_for_response(self, number, timeout_bool=True):
        for msg in self.get_unread_messages():
            msg.mark_as_read()
        timeout = datetime.now() + relativedelta(minute=10)
        if not timeout_bool:
            while 1:
                unread_msgs = self.get_unread_messages()
                filtered = unread_msgs.get(number=number)
                if len(filtered) == 0:
                    time.sleep(0.2)
                    continue
                return filtered[0]

        else:
            while datetime.now() > timeout:
                unread_msgs = self.get_unread_messages()
                filtered = unread_msgs.get(number=number)
                if len(filtered) == 0:
                    time.sleep(0.2)
                    continue
                return filtered[0]

    def on(self, event: str):
        if event not in self.allowed_events:
            raise InvalidEvent(event)

        def deco(func):
            self.events.append([event, func])

        return deco

    def request_handler(self, status_code: int):
        status_code = str(status_code)
        if status_code == '401':
            error = FailedRequest(status_code)
            print(error)

            self.auth_reset()
            return

        raise FailedRequest(status_code)
