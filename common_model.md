좋아. 그럼 **2. 공통 데이터 모델부터 맞추기** 부분을, 실제로 바로 구현 가능한 느낌으로 예시를 만들어볼게.

프로젝트 조건상 도로는 교차로와 도로 구간으로 구성되고, 차량은 slot 단위로 움직이며, i-group과 v-group은 나중에 정보를 주고받아야 하니까, 둘이 공통으로 이해할 수 있는 **같은 map / same vehicle position format / same time-step rule**을 써야 해.  

---

# 2. 공통 데이터 모델 예시

내 추천은 아래 5개를 공통으로 정의하는 거야.

1. `Node`
2. `Segment`
3. `VehicleState`
4. `IntersectionLightState`
5. `SimulationState`

---

## 2.1 Node 정의

노드는 두 종류로 나누자.

* `INTERSECTION`
* `TERMINAL`

여기서

* 9개의 원형 교차로는 `INTERSECTION`
* A, B, C, D는 `TERMINAL`

### 예시

```python id="ydsuwq"
from dataclasses import dataclass
from enum import Enum


class NodeType(Enum):
    INTERSECTION = "intersection"
    TERMINAL = "terminal"


@dataclass(frozen=True)
class Node:
    node_id: str
    node_type: NodeType
```

### 실제 노드 예시

```python id="ufh7o3"
NODES = {
    "I00": Node("I00", NodeType.INTERSECTION),
    "I01": Node("I01", NodeType.INTERSECTION),
    "I02": Node("I02", NodeType.INTERSECTION),
    "I10": Node("I10", NodeType.INTERSECTION),
    "I11": Node("I11", NodeType.INTERSECTION),
    "I12": Node("I12", NodeType.INTERSECTION),
    "I20": Node("I20", NodeType.INTERSECTION),
    "I21": Node("I21", NodeType.INTERSECTION),
    "I22": Node("I22", NodeType.INTERSECTION),

    "A": Node("A", NodeType.TERMINAL),
    "B": Node("B", NodeType.TERMINAL),
    "C": Node("C", NodeType.TERMINAL),
    "D": Node("D", NodeType.TERMINAL),
}
```

---

## 2.2 교차로 배치 이름 예시

3x3 grid니까 이렇게 두면 직관적이야.

```text id="qbje68"
I00 --- I01 --- I02
 |       |       |
I10 --- I11 --- I12
 |       |       |
I20 --- I21 --- I22
```

그리고 A, B, C, D는 바깥쪽 terminal로 연결.

예를 들어:

* A는 `I00` 왼쪽
* B는 `I02` 위쪽
* C는 `I22` 오른쪽
* D는 `I20` 아래쪽

이건 팀끼리 합의만 되면 다른 배치여도 괜찮지만, 한 번 정하면 i-group과 v-group이 똑같이 써야 해.

---

## 2.3 Segment 정의

각 도로 구간은 **방향 있는 edge**로 정의하자.

문서상 각 방향별로 single lane이므로, 양방향 도로라도 내부적으로는 **두 개의 일방향 segment**로 정의하는 게 가장 깔끔해. 차량은 매 step마다 slot에 있어야 하고, 다음 slot으로만 이동 가능하므로 segment 안에 `slot 0 ~ 29`를 둔다고 보면 돼. 

### 코드 예시

```python id="jr5fen"
@dataclass(frozen=True)
class Segment:
    segment_id: str
    from_node: str
    to_node: str
    length_slots: int = 30
```

### 실제 segment 예시

```python id="21khx7"
SEGMENTS = {
    # horizontal
    "I00_to_I01": Segment("I00_to_I01", "I00", "I01"),
    "I01_to_I00": Segment("I01_to_I00", "I01", "I00"),
    "I01_to_I02": Segment("I01_to_I02", "I01", "I02"),
    "I02_to_I01": Segment("I02_to_I01", "I02", "I01"),

    "I10_to_I11": Segment("I10_to_I11", "I10", "I11"),
    "I11_to_I10": Segment("I11_to_I10", "I11", "I10"),
    "I11_to_I12": Segment("I11_to_I12", "I11", "I12"),
    "I12_to_I11": Segment("I12_to_I11", "I12", "I11"),

    "I20_to_I21": Segment("I20_to_I21", "I20", "I21"),
    "I21_to_I20": Segment("I21_to_I20", "I21", "I20"),
    "I21_to_I22": Segment("I21_to_I22", "I21", "I22"),
    "I22_to_I21": Segment("I22_to_I21", "I22", "I21"),

    # vertical
    "I00_to_I10": Segment("I00_to_I10", "I00", "I10"),
    "I10_to_I00": Segment("I10_to_I00", "I10", "I00"),
    "I10_to_I20": Segment("I10_to_I20", "I10", "I20"),
    "I20_to_I10": Segment("I20_to_I10", "I20", "I10"),

    "I01_to_I11": Segment("I01_to_I11", "I01", "I11"),
    "I11_to_I01": Segment("I11_to_I01", "I11", "I01"),
    "I11_to_I21": Segment("I11_to_I21", "I11", "I21"),
    "I21_to_I11": Segment("I21_to_I11", "I21", "I11"),

    "I02_to_I12": Segment("I02_to_I12", "I02", "I12"),
    "I12_to_I02": Segment("I12_to_I02", "I12", "I02"),
    "I12_to_I22": Segment("I12_to_I22", "I12", "I22"),
    "I22_to_I12": Segment("I22_to_I12", "I22", "I12"),

    # terminal connections
    "A_to_I00": Segment("A_to_I00", "A", "I00"),
    "I00_to_A": Segment("I00_to_A", "I00", "A"),

    "B_to_I02": Segment("B_to_I02", "B", "I02"),
    "I02_to_B": Segment("I02_to_B", "I02", "B"),

    "C_to_I22": Segment("C_to_I22", "C", "I22"),
    "I22_to_C": Segment("I22_to_C", "I22", "C"),

    "D_to_I20": Segment("D_to_I20", "D", "I20"),
    "I20_to_D": Segment("I20_to_D", "I20", "D"),
}
```

---

## 2.4 방향 정보

차량 이동과 신호 제어를 편하게 하려면 각 segment에 방향도 연결해두는 게 좋아.

```python id="at3f45"
class Direction(Enum):
    NORTH = "north"
    SOUTH = "south"
    EAST = "east"
    WEST = "west"
```

예를 들어:

* `I00_to_I01` = EAST
* `I01_to_I00` = WEST
* `I00_to_I10` = SOUTH
* `I10_to_I00` = NORTH

이 정보가 있으면

* opposite direction check
* left turn / straight 판별
* light direction mapping
  이 쉬워진다.

---

## 2.5 VehicleState 정의

이게 i-group / v-group 모두에게 제일 중요해.

차량 하나는 최소한 아래 정보가 있어야 해:

* 현재 어느 segment에 있는지
* 그 segment의 몇 번째 slot인지
* 현재 목적지가 뭔지
* B/C/D 방문 여부
* 지금 stop 상태인지
* intersection 진입 요청이 있는지

### 코드 예시

```python id="62jvx8"
@dataclass
class VehicleState:
    car_id: str
    current_segment: str
    current_slot: int
    visited_B: bool
    visited_C: bool
    visited_D: bool
    current_target: str
    stopped: bool
    request_crossing: bool = False
    desired_next_segment: str | None = None
```

### 예시 차량 상태

```python id="x6uop7"
car_1 = VehicleState(
    car_id="car_1",
    current_segment="A_to_I00",
    current_slot=12,
    visited_B=False,
    visited_C=False,
    visited_D=False,
    current_target="B",
    stopped=False,
    request_crossing=False,
    desired_next_segment=None,
)
```

---

## 2.6 slot 표현 규칙

공통 규칙을 아주 명확히 정해야 해.

### 추천 규칙

* `slot 0` = segment의 시작점에 가장 가까운 칸
* `slot 29` = segment의 끝점, 즉 다음 교차로 바로 앞 칸
* 다음 step에서

  * 그대로 유지 가능
  * `slot+1`로 이동 가능
  * 단, `slot 29`이면 intersection crossing request 가능

이렇게 하면 v-group은 움직임 계산이 쉽고, i-group은 `slot 29` 차량만 보면 교차로 대기 차량을 알 수 있어.

---

## 2.7 IntersectionLightState 정의

i-group이 관리하는 신호등 상태도 공통 형식이 있어야 Phase B에서 붙기 쉬워.

### 가장 단순한 형태

```python id="otga8q"
@dataclass
class IntersectionLightState:
    intersection_id: str
    green_direction: str | None   # "north", "south", "east", "west" or None
```

### 예시

```python id="c55d2c"
light_I11 = IntersectionLightState(
    intersection_id="I11",
    green_direction="north"
)
```

문서상 한 시점에 최대 1개 light만 green이어야 하므로, 교차로별로 green direction 하나만 저장하면 깔끔해. 

---

## 2.8 crossing request 데이터

차량이 교차로를 통과하려면 요청 구조가 필요해.

### 코드 예시

```python id="r1fns0"
@dataclass
class CrossingRequest:
    car_id: str
    intersection_id: str
    incoming_segment: str
    outgoing_segment: str
```

### 예시

```python id="4w74b3"
req = CrossingRequest(
    car_id="car_5",
    intersection_id="I11",
    incoming_segment="I01_to_I11",
    outgoing_segment="I11_to_I12"
)
```

---

## 2.9 SimulationState 정의

전체 시뮬레이션 한 시점의 상태를 하나로 묶자.

```python id="mj3gdz"
@dataclass
class SimulationState:
    time_step: int
    vehicles: dict[str, VehicleState]
    lights: dict[str, IntersectionLightState]
```

### 예시

```python id="7btw9l"
sim_state = SimulationState(
    time_step=42,
    vehicles={
        "car_1": car_1,
    },
    lights={
        "I11": light_I11,
    }
)
```

---

# 3. i-group / v-group 공통으로 쓸 수 있는 예시 맵

아예 한 번에 보이게 정리하면 이렇게 돼.

## Node 목록

```python id="3seqav"
NODE_IDS = [
    "A", "B", "C", "D",
    "I00", "I01", "I02",
    "I10", "I11", "I12",
    "I20", "I21", "I22",
]
```

## 대표 segment 연결

```text id="tprv7h"
A <-> I00 <-> I01 <-> I02 <-> B
         |       |       |
        I10 <-> I11 <-> I12
         |       |       |
D <-> I20 <-> I21 <-> I22 <-> C
```

실제로는 각 화살표마다 양방향 segment를 따로 가진다고 보면 돼.

---

# 4. 이 데이터 모델이 좋은 이유

이 구조의 장점은:

### v-group 입장

* route planning이 쉬움
* 차량 이동을 `segment + slot`으로 단순 처리 가능
* visited B/C/D/A 관리 쉬움

### i-group 입장

* 교차로 직전 차량을 `slot 29`로 쉽게 판별 가능
* 각 incoming segment 기준으로 queue length 계산 쉬움
* green direction과 crossing arbitration 구현 쉬움

### Phase B 통합 입장

* 서로 같은 map ID, segment ID, vehicle format을 쓰므로 붙이기 쉬움
* JSON이나 dict로 그대로 message exchange 가능

---

# 5. 추천 추가 규칙

처음부터 아래 규칙도 같이 문서화해두면 좋아.

## 규칙 1

차량은 항상 정확히 하나의 위치만 가진다.

* `segment + slot`
* 교차로 내부 별도 좌표는 만들지 않음

## 규칙 2

교차로 통과는 한 step 이벤트로 처리한다.

* 현재 step에서 `slot 29`
* crossing 승인되면
* 다음 step에 outgoing segment의 `slot 0`

## 규칙 3

충돌 판단은 같은 step에 같은 `segment, slot`을 두 차량이 점유하면 collision

## 규칙 4

반대 차선 주행 금지는 segment 방향 정의로 막는다.

* 허용된 outgoing segment만 선택 가능하도록 설계

---

# 6. 바로 보고서에 넣을 수 있는 요약 문장

보고서용으로 쓰면 이런 식이야:

> We model the road system as a directed graph. Each terminal or intersection is represented as a node, and each lane direction between adjacent nodes is represented as a directed segment of 30 slots. A vehicle state is defined by its current segment and slot index, along with its destination progress and crossing request information. This unified data model is shared by both the i-group and the v-group so that the two modules can be integrated consistently in Phase B.

---

원하면 다음으로 바로 이어서
**이 데이터 모델 기준으로 v-group용 pseudo code**를 만들어줄게.
