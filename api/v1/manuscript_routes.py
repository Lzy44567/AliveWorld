"""Manuscript project endpoints; explicit analysis only, no automatic upload."""
from contextlib import contextmanager
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, StrictBool
from core.manuscript_project import ManuscriptProjects
from core.manuscript_agent import analyze_manuscript
from core.model_connections.runtime import get_task_engine
from core.session_manager import mutation_guard, MutationBusyError
from utils.runtime_paths import PATHS

router = APIRouter()
projects = ManuscriptProjects(PATHS.data_dir / 'manuscript_projects')


class CreatePayload(BaseModel):
    title: str
    source_text: str


class AnalyzePayload(BaseModel):
    expected_revision: int
    selected_text: str
    instruction: str = ''
    acknowledged: StrictBool = False


@contextmanager
def errors():
    try:
        yield
    except FileNotFoundError:
        raise HTTPException(404, '创作项目不存在') from None
    except MutationBusyError as exc:
        raise HTTPException(409, str(exc)) from None
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from None
    except OSError:
        raise HTTPException(500, '项目读写失败，请重试；没有发布资产') from None


@router.get('')
def list_projects():
    with errors():
        return {'projects': projects.list()}


@router.post('')
def create_project(payload: CreatePayload):
    with errors():
        return projects.create(payload.title, payload.source_text)


@router.get('/{project_id}')
def get_project(project_id: str):
    with errors():
        return projects.load(project_id)


@router.post('/{project_id}/analyze')
def analyze(project_id: str, payload: AnalyzePayload):
    if not payload.acknowledged:
        raise HTTPException(400, '请确认将选取文本发送到工坊接口并产生费用')
    with errors(), mutation_guard('manuscript', project_id):
        project = projects.load(project_id)
        if project['revision'] != payload.expected_revision:
            raise HTTPException(409, '项目已更新，请刷新；本次未调用模型')
        if not payload.selected_text or payload.selected_text not in project['source_text']:
            raise HTTPException(400, '请选择原稿中的连续文本')
        result = analyze_manuscript(get_task_engine('workshop'), payload.selected_text, payload.instruction)
        return projects.store_analysis(project_id, payload.expected_revision, payload.selected_text,
                                       result['candidates'], result['notes'])
