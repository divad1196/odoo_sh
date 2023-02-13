import requests
from lxml import html as lxml_html
import json
import functools
from dateutil.parser import parse as parse_date
import urllib.parse

def parse(data):
    if isinstance(data, requests.Response):
        data = data.content
    if isinstance(data, (str, bytes)):
        return lxml_html.fromstring(data)
    return None

def table2dict(table):
    res = {}
    for tr in table.xpath(".//tr"):
        key = tr.xpath(".//th")[0].text.lower()
        value = tr.xpath(".//td")[0].text.lower()
        res[key] = value
    return res

# https://stackoverflow.com/questions/16694907/download-large-file-in-python-with-requests
def download_file(session, url, local_filename):
    # NOTE the stream=True parameter below
    with session.get(url, stream=True) as r:
        r.raise_for_status()
        with open(local_filename, 'wb') as f:
            for chunk in r.iter_content(chunk_size=8192): 
                # If you have chunk encoded response uncomment if
                # and set chunk_size parameter to None.
                #if chunk: 
                f.write(chunk)
    return local_filename

PROJECT_URL = "https://www.odoo.sh/project"
GITHUB_LOGIN = "https://github.com/session"



def init_repository_data(session, repository_id):
    payload = {
        "jsonrpc":"2.0",
        "id": None,
        "method":"call",
        "params":{
            "repository_id": repository_id
        },
    }
    res = session.post(
        "https://www.odoo.sh/project/json/init",
        headers={
            "Content-Type": "application/json",
        },
        data=json.dumps(payload)
    )
    return res.json()["result"]

def get_branches_info(session, repository_id):
    res = session.post(
        "https://www.odoo.sh/web/dataset/call_kw/paas.repository/get_branches_info",
        headers={
            "Content-Type": "application/json",
            # "Referer": "https://www.odoo.sh/project/mayerbosshardt",
            # "X-Requested-With": "XMLHttpRequest",
        },
        data=json.dumps({
            "jsonrpc":"2.0",
            "id": None,
            "method":"call",
            "params":{
                "args":[repository_id],
                "model":"paas.repository",
                "method":"get_branches_info",
                "kwargs":{}
            },
        })
    )
    data = res.json()
    return data["result"]

def get_projects_data(session):
    res = session.get(PROJECT_URL)
    project_page = parse(res)
    html_projects = project_page.xpath("//div[contains(@class, 'o_project_card_container')]")
    if not html_projects:
        print("No html_projects")
        # print(lxml_html.tostring(project_page, pretty_print=True).decode())
        # Reauthorization required => TODO: automatize revalidation?
    for p in html_projects:
        a = p.xpath("div/div[1]/a")[0]
        name = a.text
        url = "https://www.odoo.sh{}".format(a.attrib["href"])
        table = p.xpath("div/table")[0]
        project_data = table2dict(table)
        yield {
            **project_data,
            "name": name,
            "url": url
        }


def build_per_branch(session, branch_id, build_limit=2):
    payload = {
        "jsonrpc":"2.0",
        "id": None,
        "method":"call",
        "params":{
            "branch_id": branch_id,
            "build_limit": build_limit,
        },
    }
    res = session.post(
        "https://www.odoo.sh/project/json/builds_per_branch",
        headers={
            "Content-Type": "application/json",
        },
        data=json.dumps(payload)
    )
    return res.json()["result"]

def polling(session, hosting_user_id, repository_id, last=0, timeout=None):
    params = {
        "channels":[],
        "last": 0, # 291150267,
        "options":{
            "paas.repository_id": repository_id,
            "paas.hosting_user_id": hosting_user_id,
            "bus_inactivity": 159650683
        }
    }
    payload = {
        "jsonrpc":"2.0",
        "id": None,
        "method":"call",
        "params": params,
    }
    url = "https://www.odoo.sh/longpolling/poll"
    res = session.post(
        url,
        headers={
            "Content-Type": "application/json",
        },
        data=json.dumps(payload),
        timeout=timeout,
    )
    return res.json()["result"]


def ask_backup(session, build_id, comment):
    payload = {
        "jsonrpc":"2.0",
        "id": None,
        "method":"call",
        "params":{
            "backup_only": 1,  # ????
            "comment": comment
        },
    }
    url = "https://www.odoo.sh/build/{build_id}/dump".format(
        build_id=build_id,
    )
    res = session.post(
        url,
        headers={
            "Content-Type": "application/json",
        },
        data=json.dumps(payload)
    )
    return res.json()["result"]

def ask_download(session, build_id, backup_datetime_utc, test_dump=True, with_filestore=False):
    test_dump = "1" if test_dump else "0"
    filestore = "1" if with_filestore else "0"
    # TODO
    payload = {
        "jsonrpc":"2.0",
        "id": None,
        "method":"call",
        "params": {
            "backup_datetime_utc": backup_datetime_utc,
            "backup_only": 0, # ?
            "test_dump": test_dump,
            "filestore": filestore,
        }
    }
    url = "https://www.odoo.sh/build/{build_id}/dump".format(
        build_id=build_id,
    )
    res = session.post(
        url,
        headers={
            "Content-Type": "application/json",
        },
        data=json.dumps(payload)
    )
    return res.json()["result"]

def list_backups(session, worker_url, build_id, branch, access_token):
    payload = {
        "jsonrpc":"2.0",
        "id": None,
        "method":"call",
        "params":{
            "token": access_token,
        },
    }
    url = "{worker_url}/paas/build/{build_id}/backups/list?branch={branch}".format(
        worker_url=worker_url,
        build_id=build_id,
        branch=branch,
    )
    res = session.post(
        url,
        headers={
            "Content-Type": "application/json",
        },
        data=json.dumps(payload)
    )
    return res.json()["result"]
class OdooShProjectBranchBuildBackup:
    def __init__(self, session, data, build):
        project = build.project
        self._session = session
        self.project = project
        self.build = build
        self.build_id = build.build_id
        self.name = data["name"]
        self.branch = data["branch"]
        self.type = data["type"]
        self.path = data["path"]
        self.downloadable = data["downloadable"]
        self.backup_datetime_utc = data["backup_datetime_utc"]
        self.date = parse_date(data["backup_datetime_utc"])
        self._data = data
    def ask_download(self, test_dump=True, with_filestore=False):
        return ask_download(
            self._session, self.build_id, self.backup_datetime_utc,
            test_dump=test_dump,
            with_filestore=with_filestore,
        )
    def download(self, file, test_dump=True, with_filestore=False):
        url = self.download_url()
        if not self.downloadable:
            # TODO: Improve this part when the backup is not downloadable
            res = self.ask_download(test_dump=test_dump, with_filestore=with_filestore)
            print(res)
            poller = self.project.poller
            while True:
                events = poller()
                print(events)
                db_dumb_ready = [
                    e.notif for e in events
                    if e.type == "notification" and e.notif.type == "db_dump_ready"
                ]
                if db_dumb_ready:
                    url = db_dumb_ready[0].url
                    break
        print(url)
        download_file(self._session, url, file)

    def download_url(self, test_dump=True, with_filestore=False):
        test_dump = "1" if test_dump else "0"
        filestore = "1" if with_filestore else "0"
        url = "{worker_url}/paas/build/{build_id}/download/dump?{params}".format(
            worker_url=self.build.worker_url,
            build_id=self.build_id,
            params=urllib.parse.urlencode({
                "test_dump": test_dump,
                "with_filestore": filestore,
                "backup_datetime_utc": self.backup_datetime_utc
            })
        )
        return url


class OdooShProjectBranchBuild:
    def __init__(self, session, data, project):
        self._session = session
        self.project = project
        self.build_id = data["id"]
        self.name = data["name"]
        self.stage = data["stage"]
        self.branch_id = data["branch_id"][0]
        self.branch = data["branch_id"][1]
        self.worker_url = data["worker_url"]
        self._data = data
        self._backups = None

    @property
    def backups(self):
        if self._backups is None:
            backups = []
            self.worker_url
            for data in list_backups(self._session, self.worker_url, self.build_id, self.branch, self.project.access_token):
                b = OdooShProjectBranchBuildBackup(self._session, data, self)
                backups.append(b)
            self._backups = backups
        return self._backups

class OdooShProjectBranch:
    def __init__(self, session, data, project):
        self._session = session
        # self._url = "{}/{}".format(project_url, branch)
        self.branch_id = data["id"]
        self.name = data["name"]
        self.stage = data["stage"]
        self.project = project
        self._builds = None
        self._data = data
    
    @property
    def builds(self):
        if self._builds is None:
            builds = []
            for data in build_per_branch(self._session, self.branch_id)[0]["builds"]:
                b = OdooShProjectBranchBuild(self._session, data, self.project)
                builds.append(b)
            self._builds = builds
        return self._builds
    
    def __repr__(self) -> str:
        return repr({
            "project": self.project,
            "branch": self.name,
            "stage": self.stage,
        })
    
    def __str__(self) -> str:
        return repr(self)

class Notification:
    type = None
    def __repr__(self):
        return repr(self.type)
    def __str__(self):
        return str(self.type)
    
    @staticmethod
    def new(session, data, project):
        name = data["name"]
        if name == "Backup Ready":
            return NotificationBackupReady(session, data, project)
        if name == "Database dump ready":
            return NotificationDBDumpReady(session, data, project)
        return None

class NotificationBackupReady(Notification):
    type = "backup_ready"
    def __init__(self, session, data, project):
        self._session = session
        self.project = project
        self.notif_id = data["id"]
        self.date = parse_date(data["create_date"])
    def __repr__(self):
        return repr({
            "Project": self.project.name,
            "Date": self.date,
            "type": self.type,
        })

class NotificationDBDumpReady(Notification):
    type = "db_dump_ready"
    def __init__(self, session, data, project):
        self._session = session
        self.project = project
        self.notif_id = data["id"]
        self.date = parse_date(data["create_date"])
        self.url = data["buttons"][0]["url"]
    def __repr__(self):
        return repr({
            "Project": self.project.name,
            "Date": self.date,
            "type": self.type,
            "url": self.url,
        })


class Event:
    type = None
    def __repr__(self):
        return repr(self.type)
    def __str__(self):
        return str(self.type)
    
    @staticmethod
    def new(session, data, project):
        name = data["message"]["type"]
        if name == "paas.hosting.user/new_notification":
            return NotificationEvent(session, data, project)
        if name == "paas.repository/backup_event":
            return None # TODO
        if name == "paas.repository/build_event":
            return None # TODO
        return None
    
class NotificationEvent:
    type = "notification"
    def __init__(self, session, data, project):
        payload = data["message"]["payload"]
        n = Notification.new(session, payload, project)
        self.event_id = data["id"]
        self.notif = n


class OdooShProject:
    def __init__(self, session, data):
        self._session = session
        self.name = data["name"]
        self.url = data["url"]
        self.version = data["version"]
        self._hosting_user_id = None
        self._repository_id = None
        self._repository_data = None
        self._access_token = None
        self._branches = None
        self._notifications = None
        self._extra_data = None
        self._data = data
    
    def __repr__(self) -> str:
        return repr(self._data)
    
    def __str__(self) -> str:
        return str(self._data)
    
    @property
    def poller(self):
        local_poller = functools.partial(polling, self._session, self.hosting_user_id, self.repository_id)
        @functools.wraps(self)
        def _poller(last=0, timeout=None):
            res = local_poller(last=last, timeout=timeout)
            events = []
            for e in res:
                event = Event.new(self._session, e, self)
                if not event:
                    continue
                events.append(event)
                if event.type == "notification":
                    self._notifications[event.notif.notif_id] = event.notif
            return events
        return _poller

    @property
    def hosting_user_id(self):
        if self._hosting_user_id is None:
            self._hosting_user_id = self.repository_data["user"]["id"]
        return self._hosting_user_id
    
    @property
    def repository_id(self):
        if self._repository_id is None:
            self._get_extra_data()
        self._repository_id = self._extra_data["repository_id"]
        return self._repository_id
    
    @property
    def repository_data(self):
        if self._repository_data is None:
            data = init_repository_data(self._session, self.repository_id)
            self._repository_data = data
        return self._repository_data

    @property
    def access_token(self):
        if self._access_token is None:
            self._access_token = self.repository_data["access_token"]
        return self._access_token

    @property
    def branches(self):
        if self._branches is None:
            self.load_branches()
        return self._branches
    
    @property
    def notifications(self):
        if self._notifications is None:
            data = self.repository_data["notifications"][str(self.repository_id)]
            notifs = {}
            for i in data["items"]:
                n = Notification.new(self._session, i, self)
                if n:
                    notifs[n.notif_id] = n
            self._notifications = notifs
        return self._notifications

    def _get_extra_data(self):
        h = parse(self._session.get(self.url))
        data = json.loads(h.xpath("//div[@id='wrapwrap']")[0].attrib["data-state"])
        self._extra_data = data
        return data

    def load_branches(self):
        branches = {}
        for data in get_branches_info(self._session, self.repository_id):
            b = OdooShProjectBranch(self._session, data, self)
            branches[b.name] = b
        self._branches = branches
        return branches


class OdooSh:
    def __init__(self, login, password):
        self._session = requests.session()
        res = self._session.get(PROJECT_URL)
        h = parse(res)
        authenticity_token = h.xpath("//input[@name='authenticity_token']")[0].value
        commit = h.xpath("//input[@name='commit']")[0].value
        res_login = self._session.post(GITHUB_LOGIN, data={
            "login": login,
            "password": password,
            "authenticity_token": authenticity_token,
            "commit": commit,
        })
        self._projects = None
    
    @property
    def projects(self):
        if self._projects is None:
            self.load_projects()
        return self._projects
    
    def load_projects(self):
        projects = {}
        for data in get_projects_data(self._session):
            p = OdooShProject(self._session, data)
            projects[p.name] = p
        self._projects = projects
        return projects
        


