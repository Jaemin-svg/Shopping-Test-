import html
import json
import os
import uuid
from datetime import datetime

import streamlit as st

DATA_FILE = "shopping_list.json"
CORRUPT_FILE = "shopping_list.corrupt.json"
MAX_NAME_LEN = 50


# ---------- 데이터 함수 ----------

def normalize_item(raw):
    """저장된 아이템을 데이터 모델에 맞게 정리한다. 쓸 수 없으면 None."""
    if not isinstance(raw, dict):
        return None
    name = raw.get("name")
    if not isinstance(name, str) or not name.strip():
        return None
    quantity = raw.get("quantity")
    if isinstance(quantity, bool) or not isinstance(quantity, (int, float)) or quantity < 1:
        quantity = 1
    item_id = raw.get("id")
    return {
        "id": item_id if isinstance(item_id, str) and item_id else uuid.uuid4().hex[:8],
        "name": name.strip()[:MAX_NAME_LEN],
        "quantity": int(quantity),
        "checked": raw.get("checked") is True,
        "created_at": raw.get("created_at") if isinstance(raw.get("created_at"), str)
        else datetime.now().isoformat(timespec="seconds"),
    }


def load_items():
    """JSON 파일에서 아이템 목록을 불러온다. 매 실행과 매 변경 때 호출한다."""
    if not os.path.exists(DATA_FILE):
        return []
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, list):
            raise ValueError("목록 형식이 아닙니다.")
    except (json.JSONDecodeError, ValueError, UnicodeDecodeError):
        # 손상된 파일은 덮어쓰지 않도록 따로 보관한다.
        os.replace(DATA_FILE, CORRUPT_FILE)
        st.session_state.load_warning = (
            f"저장된 데이터를 읽을 수 없어 빈 목록으로 시작합니다. "
            f"원래 파일은 {CORRUPT_FILE} 파일에 보관했습니다."
        )
        return []
    items = [i for i in (normalize_item(raw) for raw in data) if i is not None]
    if items != data:
        # 정리한 결과(새로 붙인 id 등)가 다음 실행에도 유지되도록 바로 저장한다.
        save_items(items)
    return items


def save_items(items):
    """아이템 목록을 JSON 파일에 저장한다. 임시 파일에 쓴 뒤 교체해 중간에 깨지지 않게 한다."""
    tmp_file = DATA_FILE + ".tmp"
    with open(tmp_file, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)
    os.replace(tmp_file, DATA_FILE)


def create_item(name, quantity=1):
    """PRD 데이터 모델에 맞는 새 아이템 dict를 만든다."""
    return {
        "id": uuid.uuid4().hex[:8],
        "name": name,
        "quantity": quantity,
        "checked": False,
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }


def find_item(items, item_id):
    """id로 아이템을 찾는다. 없으면 None."""
    for item in items:
        if item["id"] == item_id:
            return item
    return None


def validate_input(name, quantity):
    """이름과 수량을 검사해 (정리된 이름, 정수 수량, 오류 메시지)를 돌려준다."""
    name = name.strip()
    if not name:
        return name, None, "아이템 이름을 입력해 주세요."
    if len(name) > MAX_NAME_LEN:
        return name, None, f"이름은 {MAX_NAME_LEN}자 이하로 입력해 주세요. (현재 {len(name)}자)"
    if quantity is None or quantity != int(quantity) or quantity < 1:
        return name, None, "수량은 1 이상의 정수로 입력해 주세요."
    return name, int(quantity), None


# ---------- 상태 초기화 ----------

def init_state():
    """session_state에 편집 상태와 메시지를 초기화한다. 목록 자체는 매번 파일에서 읽는다."""
    defaults = {"editing_id": None, "add_error": None, "edit_error": None, "load_warning": None,
                "new_name": "", "new_qty": 1.0}
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


# ---------- 콜백 ----------
# 모든 변경은 파일을 다시 읽고 → 바꾸고 → 저장한다. 다른 탭의 변경을 덮어쓰지 않기 위해서다.

def add_item():
    """F1: 입력 폼의 값으로 아이템을 추가한다."""
    name, quantity, error = validate_input(st.session_state.new_name, st.session_state.new_qty)
    st.session_state.add_error = error
    if error:
        return
    items = load_items()
    items.append(create_item(name, quantity))
    save_items(items)
    st.session_state.new_name = ""
    st.session_state.new_qty = 1.0


def start_edit(item_id):
    """F2: 아이템을 편집 모드로 전환하고 입력창에 현재 값을 채운다."""
    item = find_item(load_items(), item_id)
    if item is None:
        return
    st.session_state.editing_id = item_id
    st.session_state.edit_error = None
    st.session_state[f"edit_name_{item_id}"] = item["name"]
    st.session_state[f"edit_qty_{item_id}"] = float(item["quantity"])


def save_edit(item_id):
    """F2: 편집한 이름과 수량을 저장한다."""
    items = load_items()
    item = find_item(items, item_id)
    if item is None:
        cancel_edit()
        return
    name, quantity, error = validate_input(st.session_state[f"edit_name_{item_id}"],
                                           st.session_state[f"edit_qty_{item_id}"])
    if error:
        st.session_state.edit_error = error
        return
    item["name"] = name
    item["quantity"] = quantity
    save_items(items)
    cancel_edit()


def cancel_edit():
    """F2: 편집을 취소한다."""
    st.session_state.editing_id = None
    st.session_state.edit_error = None


def delete_item(item_id):
    """F3: 아이템 하나를 삭제한다."""
    save_items([i for i in load_items() if i["id"] != item_id])
    if st.session_state.editing_id == item_id:
        cancel_edit()


def clear_checked():
    """F3: 체크된 아이템을 모두 삭제한다."""
    items = load_items()
    if any(i["checked"] and i["id"] == st.session_state.editing_id for i in items):
        cancel_edit()
    save_items([i for i in items if not i["checked"]])


def toggle_item(item_id):
    """F4: 체크박스 값으로 구매 완료 여부를 바꾼다."""
    items = load_items()
    item = find_item(items, item_id)
    if item is None:
        return
    item["checked"] = st.session_state[f"check_{item_id}"]
    save_items(items)


# ---------- 스타일 ----------

CSS = """
<style>
/* 전체 폭을 좁혀 목록이 한눈에 들어오게 */
.block-container { max-width: 640px; padding-top: 2.5rem; }

/* 진행 현황 */
.progress-text { font-size: 0.95rem; opacity: 0.75; margin-bottom: -0.5rem; }

/* 추가 폼: 테두리 없이 한 줄 */
[data-testid="stForm"] { border: none; padding: 0; }

/* 아이템 행: 얇은 구분선 */
[class*="st-key-row_"] {
    border-bottom: 1px solid rgba(128, 128, 128, 0.2);
    padding: 0.25rem 0.5rem;
}

/* 편집 모드 행: 연한 배경 (라이트/다크 공통으로 반투명 사용) */
[class*="st-key-row_editing_"] {
    background: rgba(255, 180, 0, 0.12);
    border-radius: 0.5rem;
}

/* 아이템 이름과 수량 */
.item-name { margin: 0 !important; word-break: break-all; }
.item-name.checked { text-decoration: line-through; opacity: 0.45; }
.item-qty { margin: 0 !important; opacity: 0.7; white-space: nowrap; }
[class*="st-key-row_"] [data-testid="stMarkdownContainer"] { margin-bottom: 0; }

/* 빈 목록 안내: 가운데 정렬된 안내 상자 (st.info는 아이콘을 왼쪽에 고정해 직접 그림) */
.empty-state {
    text-align: center;
    padding: 1rem;
    border-radius: 0.5rem;
    background: rgba(28, 131, 225, 0.1);
    color: inherit;
    margin-bottom: 1rem;
}

/* 아이콘 버튼: 작게 */
[class*="st-key-row_"] button { padding: 0.2rem 0.5rem; min-height: 2.2rem; }

/* 모바일에서도 가로 한 줄 유지 (Streamlit은 640px 이하에서 열을 세로로 쌓음) */
@media (max-width: 640px) {
    [class*="st-key-row_"] [data-testid="stHorizontalBlock"],
    [class*="st-key-add_row"] [data-testid="stHorizontalBlock"] {
        flex-wrap: nowrap;
        gap: 0.4rem;
    }
    [class*="st-key-row_"] [data-testid="stColumn"],
    [class*="st-key-add_row"] [data-testid="stColumn"] {
        min-width: 0 !important;
    }
}
</style>
"""


def inject_css():
    """페이지 전체 CSS를 주입한다."""
    st.markdown(CSS, unsafe_allow_html=True)


# ---------- 화면 ----------

def render_progress(items):
    """구매 진행 현황을 표시한다."""
    if not items:
        return
    done = sum(1 for i in items if i["checked"])
    st.markdown(f'<p class="progress-text">{done} / {len(items)}개 구매 완료</p>',
                unsafe_allow_html=True)
    st.progress(done / len(items))


def render_add_form():
    """아이템 추가 폼을 표시한다."""
    with st.form("add_form"):
        with st.container(key="add_row"):
            cols = st.columns([6, 2, 2], vertical_alignment="bottom")
            cols[0].text_input("아이템 이름", key="new_name",
                               placeholder="살 물건을 입력하세요", label_visibility="collapsed")
            cols[1].number_input("수량", key="new_qty", step=1.0, format="%g",
                                 label_visibility="collapsed")
            cols[2].form_submit_button("추가", on_click=add_item, type="primary",
                                       width="stretch")
    if st.session_state.add_error:
        st.warning(st.session_state.add_error)
        st.session_state.add_error = None


def render_item(item):
    """아이템 한 행을 표시한다."""
    item_id = item["id"]
    editing = st.session_state.editing_id == item_id
    row_key = f"row_editing_{item_id}" if editing else f"row_{item_id}"
    st.session_state[f"check_{item_id}"] = item["checked"]
    with st.container(key=row_key):
        if editing:
            cols = st.columns([1, 4, 2, 1, 1, 1], vertical_alignment="center")
            cols[0].checkbox("완료", key=f"check_{item_id}",
                             on_change=toggle_item, args=(item_id,), label_visibility="collapsed")
            cols[1].text_input("이름", key=f"edit_name_{item_id}", label_visibility="collapsed")
            cols[2].number_input("수량", key=f"edit_qty_{item_id}", step=1.0,
                                 format="%g", label_visibility="collapsed")
            cols[3].button("💾", key=f"save_{item_id}", on_click=save_edit, args=(item_id,),
                           help="저장")
            cols[4].button("✖️", key=f"cancel_{item_id}", on_click=cancel_edit, help="취소")
            cols[5].button("🗑️", key=f"del_{item_id}", on_click=delete_item, args=(item_id,),
                           help="삭제")
            if st.session_state.edit_error:
                st.warning(st.session_state.edit_error)
        else:
            cols = st.columns([1, 5, 2, 1, 1], vertical_alignment="center")
            cols[0].checkbox("완료", key=f"check_{item_id}",
                             on_change=toggle_item, args=(item_id,), label_visibility="collapsed")
            css_class = "item-name checked" if item["checked"] else "item-name"
            cols[1].markdown(f'<p class="{css_class}">{html.escape(item["name"])}</p>',
                             unsafe_allow_html=True)
            cols[2].markdown(f'<p class="item-qty">x{item["quantity"]}</p>',
                             unsafe_allow_html=True)
            cols[3].button("✏️", key=f"edit_{item_id}", on_click=start_edit, args=(item_id,),
                           help="수정")
            cols[4].button("🗑️", key=f"del_{item_id}", on_click=delete_item, args=(item_id,),
                           help="삭제")


def main():
    """앱 화면을 그린다."""
    st.set_page_config(page_title="쇼핑 리스트", page_icon="🛒", layout="centered")
    inject_css()
    init_state()
    items = load_items()
    if st.session_state.editing_id and find_item(items, st.session_state.editing_id) is None:
        cancel_edit()  # 다른 탭에서 삭제된 아이템

    st.title("🛒 쇼핑 리스트")
    if st.session_state.load_warning:
        st.warning(st.session_state.load_warning)
        st.session_state.load_warning = None
    render_progress(items)

    # 입력 영역
    render_add_form()

    # 목록 영역
    if not items:
        st.markdown('<div class="empty-state">📝 아직 추가된 아이템이 없습니다.</div>',
                    unsafe_allow_html=True)
    else:
        for item in items:
            render_item(item)

    # 하단 영역
    has_checked = any(i["checked"] for i in items)
    _, right = st.columns([3, 2])
    right.button("완료 항목 모두 삭제", key="clear_checked", on_click=clear_checked,
                 disabled=not has_checked, width="stretch")


if __name__ == "__main__":
    main()
