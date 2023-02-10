import requests
from lxml import html as lxml_html
import json

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
    def __init__(self, session, data, project):
        self._session = session
        self.project = project
        self.name = data["name"]
        self.branch = data["branch"]
        self.type = data["type"]
        self.path = data["path"]
        self.downloadable = data["downloadable"]
        self.backup_datetime_utc = data["backup_datetime_utc"]
        self._data = data

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
                b = OdooShProjectBranchBuildBackup(self._session, data, self.project)
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
        
class OdooShProject:
    def __init__(self, session, data):
        self._session = session
        self.name = data["name"]
        self.url = data["url"]
        self.version = data["version"]
        self._repository_id = None
        self._repository_data = None
        self._access_token = None
        self._branches = None
        self._data = data
    
    def __repr__(self) -> str:
        return repr(self._data)
    
    def __str__(self) -> str:
        return str(self._data)

    @property
    def repository_id(self):
        if self._repository_id is None:
            extra_data = self._extra_data()
            self._repository_id = extra_data["repository_id"]
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

    def _extra_data(self):
        h = parse(self._session.get(self.url))
        return json.loads(h.xpath("//div[@id='wrapwrap']")[0].attrib["data-state"])

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
        


