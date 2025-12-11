"""
WandB 로깅 시스템 (객체지향 설계)
- 모든 메트릭과 테이블 로깅을 중앙에서 관리
- 각 모듈에서 간단히 호출 가능
"""
import wandb
import time
from datetime import datetime
from typing import Dict, Any, List, Optional
from contextlib import contextmanager
import os


class WandbLogger:
    """WandB 로깅 통합 관리 클래스 (세션별 Run 전략)"""

    def __init__(self, project_name: str = "lawbot-kr", enabled: bool = None, run_name: str = None, tags: List[str] = None, group: str = None, session_id: str = None):
        """
        WandB 로거 초기화

        Args:
            project_name: WandB 프로젝트 이름
            enabled: 로깅 활성화 여부 (None이면 환경변수 WANDB_ENABLED로 결정)
            run_name: Run 이름 (None이면 session_id 기반 자동 생성)
            tags: 태그 리스트 (버전, 실험명 등)
            group: 그룹 이름 (None이면 날짜별 자동 그룹화)
            session_id: 세션 ID (프론트엔드에서 전달)
        """
        # 환경변수로 로깅 활성화/비활성화 제어
        if enabled is None:
            enabled = os.getenv("WANDB_ENABLED", "false").lower() == "true"

        self.enabled = enabled
        self.project_name = project_name
        self.run = None
        self.run_name = run_name
        self.tags = tags or []
        self.group = group
        self.session_id = session_id
        self.conversation_step = 0  # 세션 내 대화 턴 카운터

        # 임시 메트릭 저장소 (배치 로깅용)
        self._metrics_buffer = {}

        if self.enabled:
            self._init_wandb()

    def _init_wandb(self):
        """WandB 초기화 (세션별 Run)"""
        try:
            # 환경변수에서 버전 정보 가져오기
            version = os.getenv("LAWBOT_VERSION", "v2.0")
            experiment_name = os.getenv("WANDB_EXPERIMENT", "production")

            # 태그에 버전 추가
            tags = self.tags.copy()
            tags.append(version)
            if experiment_name:
                tags.append(experiment_name)

            # 날짜별 Group (daily_20251211)
            today = datetime.now().strftime('%Y%m%d')
            group = self.group or os.getenv("WANDB_GROUP", f"daily_{today}")

            # Run 이름: 세션 ID 기반 (session_abc123_143022)
            run_name = self.run_name
            if not run_name:
                if self.session_id:
                    # 세션 ID에서 timestamp 추출 (session-1702345678 형식)
                    timestamp = datetime.now().strftime('%H%M%S')
                    run_name = f"{self.session_id}_{timestamp}"
                else:
                    run_name = f"session_unknown_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

            self.run = wandb.init(
                project=self.project_name,
                name=run_name,
                tags=tags,
                group=group,
                config={
                    "model": "gemini-2.5-flash",
                    "embedding_model": "intfloat/multilingual-e5-large-instruct",
                    "vector_db": "supabase",
                    "chunking": "article-based",
                    "version": version,
                    "experiment": experiment_name,
                    "session_id": self.session_id
                },
                # 세션별 run이므로 resume 사용 안 함
                resume="never"
            )

            print(f"✅ WandB 초기화 완료: {self.project_name}")
            print(f"   Run: {self.run.name}")
            print(f"   Group: {self.run.group}")
            print(f"   Tags: {self.run.tags}")
            print(f"   Session: {self.session_id}")
        except Exception as e:
            print(f"⚠️ WandB 초기화 실패: {e}")
            self.enabled = False

    def log_metric(self, key: str, value: Any, step: Optional[int] = None):
        """단일 메트릭 로깅 (step 자동 증가)"""
        if not self.enabled:
            return

        try:
            # step이 없으면 conversation_step 사용
            if step is None:
                step = self.conversation_step

            wandb.log({key: value}, step=step)
        except Exception as e:
            print(f"⚠️ 메트릭 로깅 실패 ({key}): {e}")

    def log_metrics(self, metrics: Dict[str, Any], step: Optional[int] = None):
        """여러 메트릭 한번에 로깅 (step 자동 증가)"""
        if not self.enabled:
            return

        try:
            # step이 없으면 conversation_step 사용
            if step is None:
                step = self.conversation_step

            wandb.log(metrics, step=step)
        except Exception as e:
            print(f"⚠️ 메트릭 배치 로깅 실패: {e}")

    def increment_step(self):
        """대화 턴 증가 (새 질문마다 호출)"""
        self.conversation_step += 1
        return self.conversation_step

    def log_table(self, table_name: str, columns: List[str], data: List[List[Any]]):
        """테이블 로깅"""
        if not self.enabled:
            return

        try:
            table = wandb.Table(columns=columns, data=data)
            wandb.log({table_name: table})
        except Exception as e:
            print(f"⚠️ 테이블 로깅 실패 ({table_name}): {e}")

    @contextmanager
    def timer(self, metric_name: str):
        """실행 시간 측정 컨텍스트 매니저"""
        start_time = time.time()
        try:
            yield
        finally:
            elapsed_time = time.time() - start_time
            self.log_metric(metric_name, elapsed_time)

    def finish(self):
        """WandB 세션 종료"""
        if self.enabled and self.run:
            wandb.finish()


class AgenticRAGLogger:
    """AgenticRAG 전용 로거"""

    def __init__(self, wandb_logger: WandbLogger):
        self.logger = wandb_logger
        self.session_start = None
        self.tool_calls_log = []
        self.conversation_log = []

    def start_session(self, question: str):
        """세션 시작 (대화 턴 증가)"""
        self.session_start = time.time()
        self.tool_calls_log = []

        # 대화 턴 증가
        self.logger.increment_step()

        return {
            "question": question,
            "timestamp": datetime.now().isoformat(),
            "step": self.logger.conversation_step
        }

    def log_tool_call(self, tool_name: str, args: Dict, result_preview: str, execution_time: float, success: bool = True):
        """도구 호출 로깅"""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "tool_name": tool_name,
            "args": str(args),
            "result_preview": result_preview[:100] if result_preview else "",
            "execution_time": execution_time,
            "success": success
        }
        self.tool_calls_log.append(log_entry)

        # 메트릭 로깅
        self.logger.log_metrics({
            f"tool/{tool_name}/execution_time": execution_time,
            f"tool/{tool_name}/success": 1 if success else 0
        })

    def end_session(self, answer: str, total_tokens: Optional[int] = None):
        """세션 종료 및 로깅"""
        if self.session_start is None:
            return

        total_time = time.time() - self.session_start

        # 메트릭 로깅
        metrics = {
            "agentic_rag/total_execution_time": total_time,
            "agentic_rag/tool_calls_count": len(self.tool_calls_log),
            "agentic_rag/answer_length": len(answer)
        }

        if total_tokens:
            metrics["agentic_rag/total_tokens"] = total_tokens

        self.logger.log_metrics(metrics)

        # 도구 호출 테이블 로깅
        if self.tool_calls_log:
            self.logger.log_table(
                "tool_calls_log",
                ["timestamp", "tool_name", "args", "result_preview", "execution_time", "success"],
                [[log["timestamp"], log["tool_name"], log["args"], log["result_preview"],
                  log["execution_time"], log["success"]] for log in self.tool_calls_log]
            )

        self.session_start = None


class VectorSearchLogger:
    """벡터 검색 전용 로거"""

    def __init__(self, wandb_logger: WandbLogger):
        self.logger = wandb_logger
        self.search_logs = []

    def log_search(
        self,
        query: str,
        search_time: float,
        embedding_time: float,
        results_count: int,
        top_similarity: float,
        search_method: str,  # "RPC" or "Fallback"
        deduplication_count: int = 0
    ):
        """벡터 검색 로깅"""
        # 메트릭 로깅
        self.logger.log_metrics({
            "vector_search/search_latency": search_time,
            "vector_search/embedding_time": embedding_time,
            "vector_search/results_count": results_count,
            "vector_search/top_similarity": top_similarity,
            "vector_search/deduplication_count": deduplication_count,
            f"vector_search/method/{search_method.lower()}": 1
        })

        # 검색 로그 저장
        self.search_logs.append({
            "timestamp": datetime.now().isoformat(),
            "query": query[:50],
            "search_time": search_time,
            "results_count": results_count,
            "top_similarity": top_similarity,
            "search_method": search_method,
            "deduplication_count": deduplication_count
        })

    def flush_search_logs(self):
        """검색 로그 테이블로 플러시"""
        if not self.search_logs:
            return

        self.logger.log_table(
            "vector_search_log",
            ["timestamp", "query", "search_time", "results_count", "top_similarity", "search_method", "deduplication_count"],
            [[log["timestamp"], log["query"], log["search_time"], log["results_count"],
              log["top_similarity"], log["search_method"], log["deduplication_count"]]
             for log in self.search_logs]
        )

        self.search_logs = []


class LawAPILogger:
    """법령 API 전용 로거"""

    def __init__(self, wandb_logger: WandbLogger):
        self.logger = wandb_logger
        self.api_logs = []
        self.error_logs = []

    def log_api_call(
        self,
        endpoint: str,
        law_name: str,
        article: Optional[str],
        response_time: float,
        status_code: int,
        success: bool,
        error_message: Optional[str] = None
    ):
        """API 호출 로깅"""
        # 메트릭 로깅
        self.logger.log_metrics({
            f"law_api/{endpoint}/response_time": response_time,
            f"law_api/{endpoint}/success": 1 if success else 0,
            "law_api/total_calls": 1
        })

        # API 로그 저장
        api_log = {
            "timestamp": datetime.now().isoformat(),
            "endpoint": endpoint,
            "law_name": law_name,
            "article": article or "",
            "response_time": response_time,
            "status_code": status_code,
            "success": success
        }
        self.api_logs.append(api_log)

        # 에러 로깅
        if not success and error_message:
            self.error_logs.append({
                "timestamp": datetime.now().isoformat(),
                "error_type": endpoint,
                "error_message": error_message[:200],
                "law_name": law_name,
                "article": article or ""
            })

    def flush_logs(self):
        """로그 테이블로 플러시"""
        # API 호출 로그
        if self.api_logs:
            self.logger.log_table(
                "law_api_calls_log",
                ["timestamp", "endpoint", "law_name", "article", "response_time", "status_code", "success"],
                [[log["timestamp"], log["endpoint"], log["law_name"], log["article"],
                  log["response_time"], log["status_code"], log["success"]]
                 for log in self.api_logs]
            )
            self.api_logs = []

        # 에러 로그
        if self.error_logs:
            self.logger.log_table(
                "law_api_errors_log",
                ["timestamp", "error_type", "error_message", "law_name", "article"],
                [[log["timestamp"], log["error_type"], log["error_message"], log["law_name"], log["article"]]
                 for log in self.error_logs]
            )
            self.error_logs = []


class FastAPILogger:
    """FastAPI 엔드포인트 전용 로거"""

    def __init__(self, wandb_logger: WandbLogger):
        self.logger = wandb_logger
        self.request_logs = []
        self.active_sessions = set()

    def log_request(
        self,
        session_id: str,
        question: str,
        answer_length: int,
        response_time: float,
        status_code: int,
        error_message: Optional[str] = None
    ):
        """API 요청 로깅"""
        self.active_sessions.add(session_id)

        # 메트릭 로깅
        metrics = {
            "fastapi/request_count": 1,
            "fastapi/avg_response_time": response_time,
            "fastapi/concurrent_users": len(self.active_sessions),
            "fastapi/answer_length": answer_length
        }

        if error_message:
            metrics["fastapi/error_rate"] = 1
        else:
            metrics["fastapi/error_rate"] = 0

        self.logger.log_metrics(metrics)

        # 요청 로그 저장
        self.request_logs.append({
            "timestamp": datetime.now().isoformat(),
            "session_id": session_id,
            "question": question[:50],
            "answer_length": answer_length,
            "response_time": response_time,
            "status_code": status_code,
            "error": error_message or ""
        })

    def flush_logs(self):
        """로그 테이블로 플러시"""
        if not self.request_logs:
            return

        self.logger.log_table(
            "fastapi_requests_log",
            ["timestamp", "session_id", "question", "answer_length", "response_time", "status_code", "error"],
            [[log["timestamp"], log["session_id"], log["question"], log["answer_length"],
              log["response_time"], log["status_code"], log["error"]]
             for log in self.request_logs]
        )

        self.request_logs = []


# ========================================
# 세션별 인스턴스 관리 (싱글톤 대신 세션 기반)
# ========================================

_wandb_logger_instances = {}  # session_id -> WandbLogger 매핑

def get_wandb_logger(session_id: str = None) -> WandbLogger:
    """
    WandB 로거 인스턴스 가져오기 (세션별)

    Args:
        session_id: 세션 ID (없으면 전역 인스턴스 사용)

    Returns:
        WandbLogger 인스턴스
    """
    global _wandb_logger_instances

    # 세션 ID 없으면 기본 인스턴스 사용 (하위 호환성)
    if session_id is None:
        session_id = "default"

    # 세션별 인스턴스가 없으면 생성
    if session_id not in _wandb_logger_instances:
        _wandb_logger_instances[session_id] = WandbLogger(session_id=session_id)

    return _wandb_logger_instances[session_id]


def cleanup_wandb_logger(session_id: str):
    """
    세션 종료 시 WandB run 정리

    Args:
        session_id: 종료할 세션 ID
    """
    global _wandb_logger_instances

    if session_id in _wandb_logger_instances:
        logger = _wandb_logger_instances[session_id]
        logger.finish()
        del _wandb_logger_instances[session_id]
        print(f"✅ WandB 세션 종료: {session_id}")
