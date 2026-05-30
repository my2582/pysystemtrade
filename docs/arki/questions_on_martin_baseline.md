Martin의 논문 완독 후 내 질문에 답할 준비해주세요
---
읽었습니다. 핵심 구조와 결과를 정리해 두었으니 질문 주시면 됩니다.

**논문의 중심 명제**
시장 수익률이 대칭(skew=0)이어도 momentum/trend-following 전략의 *trading return*은 양의 왜도를 갖는다. 이 왜도는 자산군의 속성이 아니라 **전략 설계(position-sizing)의 산물**이며, long-only equity/credit의 내재적 음의 왜도와 대비된다. 핵심 메커니즘은 "돈을 번 뒤 포지션을 키우는" 구조 → 고분산 성분이 양의 평균을 가짐 → 양의 왜도.

**Linear strategies (§2)**
- $\varphi_n=\sum_j a_j U_{n-j}$, 2nd moment $=M R_0^a$, 3rd moment $=6\sum_{k=1}^{M-1}(M-k)a_{k-1}R_k^a$ (식 12).
- 모든 $a_j>0$ → 양의 왜도 보장 / counter-trending → 음의 왜도.
- 왜도 term structure: 0에서 시작 → peak → $M^{-1/2}$로 감쇠. EMA1 max skew ≈ 2.41 at $M\approx1.07N$, EMA2 ≈ 2.1 at $M\approx1.7(N_\alpha+N_\beta)$.
- $M^{-1/2}$ 점근은 Lévy와 같지만 기원이 반대: 여기선 one-period returns가 **대칭이지만 독립이 아님**.
- Path-length 관점에서 EMA2가 EMA1보다 선호됨(transaction cost). 변분문제 해 $te^{-\dot\alpha t}$ = EMA2=가 최적 필터.

**Option-like 구조 (§3)**
$Y^{(M)}=u'\Gamma u$, $\langle Y^3\rangle=8\,\mathrm{tr}(\Gamma^3)$. 소수의 큰 양의 고유값(long-dated options 매수) + 다수의 작은 음의 고유값(short-dated 매도). 장기 변동성↑·단기 변동성↓ 국면에서 유리.

**Nonlinear strategies (§4)**
- $\varphi_n=\psi(V_n)$, $H_k=2a_{k-1}\langle\psi(Z_1)\psi'(Z_1)\psi(Z_2)\rangle_{\rho=R_k^a}$ (식 29).
- **Simple sigmoid**: capping → max skew 감소(수직 압축).
- **Reverting sigmoid** $ze^{-\lambda^2z^2/2}$: 강한 추세에서 포지션 축소, $\lambda\gtrsim1.3$이면 왜도가 음으로 전환. 2014 oil 매도 같은 장기 추세에서 큰 손실(Fig 9).
- **Double-step**: $\epsilon\to0$(binary sgn) → 왜도 소멸. SR은 $\epsilon<0.6$에서 평평하므로 $\epsilon\approx0.6$이 sweet spot.

**설계 결론 (§5)**
1. Binary ±1 bet은 나쁨 → threshold 도입이 개선책.
2. 고momentum에서 포지션을 *cap*보다 *reduce*하는 게 낫지만 과하면 안 됨(음의 왜도·과잉거래·대형추세 수익 상실).
3. Calibration은 데이터 히스토리에 민감 → 시나리오 기반 설계 권장(순수 historical SR 추종 지양).

---
아래가 martin 연구를 실증할 베이스라인으로 적절한지?

Strategy spec — Martin baseline (single-instrument 6-speed EWMAC)

EWMAC speeds: ewmac2_8, ewmac4_16, ewmac8_32, ewmac16_64, ewmac32_128, ewmac64_256. Forecast weights: equal (1/6 each). Carry rule OFF.
Capital $50,000. Vol target 20%. Forecast cap +-20 (soft). Integer contracts.
Trade unit = position roundtrip (0 -> non-0 -> 0). Position source = engine actual buffered.
Evidence pack: ars/evidence_packs/martin_single_instrument/ (5/5 gates PASS, Path Z grandfather).
---
단도직입적으로: **조건부 적절**입니다. Carver식 6-speed EWMAC는 Martin의 §2.5 실증 셋업(단일 instrument, CHFUSD/SPX futures)과 구조적으로 잘 맞고, 특히 carry OFF·vol-normalized 포지션·all-positive 가중치라는 점에서 "pure linear trend" 가정의 영역 안에 들어옵니다. 다만 지금 spec 그대로는 *Martin 이론을 검증*하는 게 아니라 *Martin 효과의 잔존 여부를 관측*하는 데 그칠 위험이 있습니다. 아래 세 가지가 핵심입니다.

**1. 가장 큰 리스크 — 3중 비선형성이 왜도를 0쪽으로 압축**

Martin의 깨끗한 예측(peak skew ≈ 2.1, $M^{-1/2}$ 감쇠)은 *연속·비절단 포지션*에서만 성립합니다. 현재 spec에는 왜도를 깎아내리는 비선형성이 셋 겹쳐 있습니다:

- **Forecast cap ±20 (soft)** → §4.2.1 simple sigmoid와 동일한 capping. 효과는 term structure의 수직 압축(peak가 ~2.1 → ~1.5–1.9로 내려감). Fig 5(b) 모양과 *일관*되지만, 이 상태로 "linear baseline"을 주장할 수는 없음.
- **Integer contracts** → §4.2.3 double-step에 접근. 이게 결정적입니다.
- **Buffered actual position** → 추가적 경로의존·계단화.

특히 **$50,000 capital + single instrument + integer**의 조합이 위험합니다. 20% vol target에서 contract notional이 크면 (예: full-size CL ~$60k/계약) 포지션이 사실상 {0,1,2} 계단으로 양자화되고, 이는 Martin이 *왜도를 소멸시킨다*고 명시한 binary/step regime입니다. 그러면 term structure가 안 나와도 그건 Martin이 틀린 게 아니라 discretization이 선형성을 파괴한 것.

→ **micro contracts (MES/MCL/M2K 등) 필수**, 또는 capital을 키워 integer level이 충분히 조밀해지게 할 것. 그리고 검증용으로는 **continuous(반올림·버퍼 이전) optimal position**을 별도 position source로 측정해 execution friction과 Martin 효과를 분리해야 합니다. "engine actual buffered"는 *realism* 트랙으로만 두세요.

**2. Deliverable은 단일 왜도가 아니라 term structure 곡선이어야 함**

Martin의 중심 결과는 skewness as a function of return period $M$ (Fig 2,3)입니다. 검증의 최소 형태는:

- $M \in \{1,2,5,10,20,50,100,150,200,250\}$ 일에 대해 $M$-period trading-return 왜도 sweep
- **central skew와 non-central skew를 동시에** 산출 (실데이터는 mean≠0이므로 — §2.5)
- 결합 impulse response에 대한 **theoretical 곡선 overlay** (eq 18/19)
- "skew는 자산이 아니라 sizing에서 온다"는 핵심 주장 검증을 위해 **underlying $U_n$의 왜도도 같이 보고** (Martin: CHF≈0.0, SPX≈−0.2 vs trading-return≈2). 이 대비가 money-shot.

"5/5 gates PASS"가 단일 skew 임계치 게이트라면 Martin 검증으로는 불충분합니다. gate가 곡선 형상($M^{-1/2}$ tail, peak 위치)을 검정하는지 확인 필요.

**3. 6-speed 결합은 정성 검증용 — 폐형식 검증엔 single-speed**

각 EWMAC는 EMA2(= double-EMA of returns, 모든 $a_j>0$)이고 equal positive weight 합성도 aggregate $a_j>0$ → Martin은 양의 왜도를 예측합니다. 여기까진 정합. 하지만 합성하면 peak 위치/높이가 단일 속도 공식($M\approx 1.7(N_\alpha+N_\beta)$, max≈2.1)과 직접 안 맞습니다.

- **정성 주장**(양의 skew 존재, term structure 형상, sizing 기원) 검증 → 6-speed로 OK
- **폐형식 공식**(peak 값, EMA1 vs EMA2 max skew, $M^{-1/2}$) 검증 → **single-speed EMA2 variant**를 cap OFF로 별도 실행해 eq (17)/(19)와 직접 대조

**부차 사항**
- Vol estimator: Martin은 20-day EMA of squared changes. Carver 기본(보통 36일/blend)과 다르므로, fidelity가 목적이면 20-day로 맞추는 게 좋습니다. (결과에 결정적이진 않음.)
- 통계: overlapping $M$-day returns는 자기상관으로 effective N을 줄여 skew 표준오차가 큽니다. **bootstrap CI** 첨부 권장. 단일 instrument·장기 히스토리(≥20y)는 §2.5와 동일하므로 적절.

---

**정리된 권고**: 같은 엔진에서 두 트랙으로 분리하세요.

| 트랙 | 설정 | 검증 대상 |
|---|---|---|
| **Theory** | single-speed EMA2, cap OFF, continuous position, 20d vol | eq 17/19 peak·$M^{-1/2}$ 폐형식 |
| **Realistic** | 6-speed, cap ±20, integer buffered (micro) | 정성 주장 + execution 영향 |

현재 spec은 Realistic 트랙으로는 합격선이지만, "Martin baseline"이라는 이름을 달려면 Theory 트랙과 term-structure sweep + $U_n$ 대비가 빠지면 검증이 성립하지 않습니다. 진행하시겠어요, 아니면 Theory 트랙 spec을 먼저 확정할까요?
---
아래 스펙으로 이어서 검증하려고 합니다
Strategy spec — Martin baseline + sMOM overlay (PROMOTED 2026-05-29)
Trades are identical to Martin baseline because sign(w_sMOM,t) is always positive (downside-vol scaler never flips). Per-trade ledger therefore matches baseline; system NAV (top of report) is sMOM-overlaid and reflects the +0.255 Sharpe lift.
w_sMOM,t = sqrt(target_var) / sqrt(semi_var_126d), normalised so std(R_sMOM) = std(R_baseline) ex-post (closed-form lambda).
Evidence pack: ars/evidence_packs/smom_us10/ · pre-reg locked at 28e4b629.
---
결론부터: **이 spec은 "Martin 검증"과 "sMOM 성과 주장"이라는 *서로 다른 두 클레임*을 하나의 PROMOTED 패키지에 섞어놨고, 그 중 하나는 논리적으로 자기모순**입니다. sMOM 자체는 합리적인 overlay지만, 지금 문장 그대로 evidence pack에 들어가면 리뷰에서 막힙니다.

**1. 맞는 부분 (그대로 가도 됨)**

- $w_{sMOM,t} = \sqrt{\text{target\_var}}/\sqrt{\text{semi\_var}_{126d}}$ 는 분자·분모 모두 표준편차 → **항상 양수**. 따라서 $\text{sign}(w\cdot\varphi)=\text{sign}(\varphi)$, **zero-crossing 타이밍과 방향은 baseline과 동일**. roundtrip 정의(0→non-0→0)상 진입일·청산일·direction이 보존된다는 주장은 **참**입니다.
- 전역 상수 $\lambda$로 ex-post std를 맞추는 것: Sharpe는 scale-invariant이므로 $\lambda$ 선택이 **+0.255 수치 자체를 오염시키지 않음**. 즉 lift는 time-varying $w_t$에서 나오는 것이고 $\lambda$는 표시용. 이 부분은 깨끗합니다.

**2. 자기모순 — "ledger matches baseline" vs "NAV reflects +0.255 lift"**

이 둘은 동시에 참일 수 없습니다. Lift는 **매 기간 position size를 바꾼 데서** 나옵니다 ($w_t$가 time-varying). 그러면 per-trade P&L이 baseline과 다를 수밖에 없고, P&L이 다르면 NAV가 다른 게 당연합니다. **per-trade P&L이 동일한데 NAV만 다르다는 건 불가능**합니다.

해소 경로는 하나뿐입니다 — ledger가 무엇을 기록하느냐:

- **(A) Blotter 읽기**: ledger = {entry, exit, direction, instrument}만 기록, P&L 없음 → "matches baseline" 참. Lift는 position-path scaling에서 발생. **이 경우 spec은 정합하지만 "therefore"가 오독 유발** → "trade blotter (timing+direction) matches; per-period sizing and trade-level P&L differ by $w_t$"로 명시 필요.
- **(B) P&L 포함 읽기**: 주장 모순. 폐기.

어느 쪽입니까? (A)라면 문구만 고치면 됩니다.

**3. 진짜 문제 — sMOM은 Martin 검증의 confound입니다**

Martin의 폐형식(식 12, 27)은 position이 $\varphi_n=\psi(V_n)$, 즉 **U들의 momentum filter만의 함수**라는 전제 위에 있습니다. sMOM은 여기에 $w_t$라는 추가 인자를 곱하는데, $\text{semi\_var}_{126d}$는 **과거 음의 수익률 제곱의 가중합** — 즉 Martin의 $\psi$에 없는 *별도의 비선형·경로의존 항*입니다.

따라서:

- **Martin term-structure 검증은 반드시 baseline trades에서만** 돌려야 합니다. sMOM-overlaid NAV/returns는 Martin 검증의 유효 대상이 **아닙니다**. 한 spec 안에 PROMOTED로 묶으면 Martin evidence가 오염됩니다.
- 더 중요한 점: **sMOM은 skewness를 바꿉니다.** Downside-vol이 높을 때 de-lever하는 구조는 좌측 꼬리를 깎지만 **우측(추세 수익) 꼬리도 함께 클립**할 수 있습니다. 이건 Martin이 §4.4·§5에서 강조한 바로 그 **SR↔skew trade-off**입니다 — Till & Eagleeye 인용 그대로, "higher Sharpe is a form of remuneration for negative skewness."

→ **+0.255 Sharpe lift를 "free lift"로 promote하기 전에, $\kappa_3(R_{sMOM})$ vs $\kappa_3(R_{baseline})$를 반드시 측정**하세요. lift가 왜도 감소를 대가로 한 것이라면, 당신의 GTAA overlay 맥락(positive skew = longevity)에서는 오히려 역효과일 수 있습니다. Sharpe만 보고 promote하는 건 Martin 논문 전체 논지에 정면으로 반합니다.

**4. Pre-reg 위생**

`28e4b629` lock + Path Z grandfather는 좋습니다. 다만 ex-post $\lambda$ 정규화가 들어간 헤드라인 NAV를 promote 근거로 쓰면, NAV path는 tradeable equity curve가 아닌 **표시용 구성물**임을 패키지에 박아두세요. 그리고 pre-reg에 (a) Martin 검증=baseline only, (b) sMOM lift = trailing semivar·OOS-feasible, (c) $\kappa_3(R_{sMOM})$ 동시 보고 — 세 가지가 분리 명시돼야 합니다.

---

**권고**: evidence pack을 두 개로 쪼개세요.

| Pack | 대상 | 헤드라인 |
|---|---|---|
| `martin_single_instrument/` | baseline trades | skew term structure vs eq 17/19, $\kappa_3$(trading) vs $\kappa_3(U_n)$ |
| `smom_us10/` | sMOM-overlaid NAV | +0.255 SR **+ Δskew** 동시 |

현 상태에서 막힌 건 #2(문구 정합)와 #3(skew 미측정) 둘입니다. blotter 읽기(A)가 맞는지, 그리고 $\kappa_3(R_{sMOM})$를 이미 산출했는지 — 이 두 개만 확인되면 promote 가능 여부가 갈립니다. 어느 쪽인가요?


---
Martin 논문 설명 중 Linear strategies (§2) 를 이해하기 쉽게 풀어서 설명


---
§2의 핵심은 한 문장입니다: **"선형 전략에서는 포지션 가중치 $a_j$가 모두 양수이기만 하면, 시장 수익률이 완벽히 대칭이어도 거래 수익의 왜도는 반드시 양수다."** 이걸 왜·어떻게 보이는지를 단계별로 풀어보겠습니다.

**1. "Linear strategy"가 뭔가 (§2.1)**

포지션을 과거 수익률들의 **가중합**으로 잡는 전략입니다:

$$\varphi_n = \sum_{j=0}^{\infty} a_j U_{n-j}$$

여기서 $U_{n-j}$는 vol로 정규화한 과거 수익률, $a_j$는 "$j$일 전 수익률에 얼마의 비중을 둘까"입니다. EWMAC를 떠올리면 됩니다 — 사실상 과거 수익률의 EMA가 곧 포지션이 되는 구조죠.

선형이라서 좋은 점 세 가지:
- **재귀 계산 가능**: EMA라 한 줄 업데이트.
- **더하기가 자유로움**: 속도가 다른 momentum들을 그냥 합치면 됨 (당신의 6-speed가 바로 이것).
- **분석이 깔끔**: 거래 수익의 모든 moment를 가중치 $a_j$만으로 표현 가능.

두 가지 building block:
- **EMA1**: $a_j = \alpha^{j+1}$. spot price와 EMA의 차이. 가장 단순.
- **EMA2**: 빠른 EMA − 느린 EMA. 하루하루 변동이 더 매끄러워서 **거래비용 측면에서 EMA2를 선호**(§2.2의 path-length 논증 — EMA1은 경로 길이가 무한, EMA2는 유한).

분석 도구 두 개만 기억하면 됩니다:
- 자기공분산 $R_k^a = \sum_j a_j a_{j+k}$ — 가중치 패턴이 $k$만큼 어긋났을 때의 겹침.
- system function $A(z) = \sum_j a_j z^{-j}$ — 가중치의 z-변환. 극점(pole) 위치가 설계의 핵심.

**2. 2차 moment는 시시하고, 3차 moment에 전부가 있다 (§2.3)**

$M$일 거래 수익 $Y^{(M)} = \sum_{k=0}^{M-1}\varphi_{n+k}U_{n+k+1}$의 분산은 그냥:

$$\langle (Y^{(M)})^2\rangle = M R_0^a$$

$M$에 **선형**으로 커집니다 (거래 수익끼리 무상관이라). 재미없습니다.

3차 moment(왜도의 분자)가 핵심입니다:

$$\langle (Y^{(M)})^3\rangle = 6\sum_{k=1}^{M-1}(M-k)\,a_{k-1}R_k^a \quad (\text{식 12})$$

여기서 **모든 $a_j > 0$이면 우변이 무조건 양수** → 양의 왜도가 수학적으로 보장됩니다. 반대로 counter-trend(가중치 음수)는 음의 왜도.

**왜 그런가 — 직관 (가장 중요한 부분)**

3차 moment를 전개하면 네 종류 항이 나오는데, 가정($U$들이 독립·평균0·왜도0) 때문에 셋이 사라지고 **딱 한 종류만 살아남습니다**:

$$\varphi_n^2 U_{n+1}^2 \,\varphi_m U_{m+1}, \quad n>m$$

이게 0이 아닌 이유: $\varphi_n$(오늘 포지션)이 과거 수익률 $U_{m+1}$을 *포함*하기 때문입니다. 말로 풀면 — **"과거에 수익이 났던($U_{m+1}>0$) 자산에는 지금 더 큰 포지션($\varphi_n$ 큼)을 들고 있고, 그 큰 포지션이 만든 P&L의 분산도 크다."** 즉 큰 변동성을 가진 P&L 성분이 양의 평균을 갖는 구조 → 양의 왜도의 정의 그 자체입니다.

→ **시장이 대칭이어도, "이긴 뒤에 키운다"는 sizing 규칙 하나만으로 왜도가 생긴다.** 이게 §2 전체의 메시지입니다.

**3. 왜도의 모양 — term structure (§2.4)**

왜도를 기간 $M$의 함수로 보면 특징적인 곡선이 나옵니다:

- $M=1$에서 **0**에서 출발 (하루짜리는 왜도 없음)
- 어떤 $M$에서 **peak**
- 이후 $M^{-1/2}$로 천천히 **감쇠**

폐형식으로:

**EMA1** (식 17):
$$\kappa_3^{(M)} = \frac{6\alpha}{(1-\alpha^2)^{1/2}M^{1/2}}\left(1 - \frac{1-\alpha^{2M}}{1-\alpha^2}M^{-1}\right)$$
peak skew ≈ **2.41**, 위치 $M \approx 1.07N$ (여기서 $\alpha = 1-N^{-1}$).

**EMA2** (식 18/19): 형태는 비슷, peak ≈ **2.1**, 위치 $M\approx 1.7(N_\alpha+N_\beta)$.

흥미로운 디테일: $M^{-1/2}$ 감쇠는 Lévy process와 똑같은데 **기원이 정반대**입니다. Lévy는 "one-period 수익이 비대칭이지만 독립"이라서 생기고, 여기선 "one-period 수익이 **대칭이지만 독립이 아니라서**" 생깁니다. 비대칭 분포를 *대칭* 확률변수들의 합으로 만들어낸 셈 — 의존성이 비대칭을 빚어냅니다.

**4. 실데이터 검증 (§2.5)**

CHFUSD·S&P500 futures(20년+, EMA2 N=20,40)에 적용한 결과:
- 이론 곡선(Fig 2b)과 실측이 형상에서 잘 맞음.
- **결정적 대비**: 시장 자체($U_n$)의 왜도는 CHF≈0.0, SPX≈−0.2인데, **거래 수익의 왜도는 ≈2**. → 왜도는 자산이 아니라 **전략에서 나온다**는 주장의 실증.
- mean≠0 보정을 위해 central skew와 non-central skew를 둘 다 plot (앞서 검증 spec에서 둘 다 보고하라고 한 이유).

**5. Hybrid — trend + counter-trend 섞기 (§2.6)**

추세추종에 약간의 역추세를 섞고 싶을 때 (단기 reversion 베팅, 또는 장기 과열에 대한 소량 반대 베팅). 일부 $a_j$가 음수가 되죠. 문제는 "음수를 어디까지 허용해야 장기 왜도가 여전히 양수냐"입니다.

빠른/느린 EMA2를 $\lambda_F, \lambda_S$로 결합하면, 양의 점근 왜도 조건이 깔끔한 부등식으로 떨어집니다. $N_{\alpha F}=5, N_{\beta F}=10, N_{\alpha S}=20, N_{\beta S}=40$ 예시에서:

$$\lambda_F + 1.476\,\lambda_S > 0$$

→ 이걸 최적화에 **style constraint**로 그냥 박아 넣으면 됩니다. counter-trend를 섞되 longevity(양의 왜도)를 잃지 않는 선을 명시적으로 그어주는 것. 당신의 trade-management overlay 설계에 직접 쓸 수 있는 형태입니다.

---

한 줄 요약: **선형 추세전략의 양의 왜도는 시장의 성질이 아니라 "이긴 포지션을 키운다"는 sizing의 산물이고, 그 왜도는 기간에 따라 0→peak→$M^{-1/2}$로 움직이며, 가중치 부호 조건만 관리하면 hybrid에서도 보존된다.** 더 깊이 들어갈 부분(예: §2.4의 residue calculus 유도, 또는 hybrid constraint를 6-speed에 적용)이 있으면 짚어드리겠습니다.


---
U_{n-j}는 vol로 정규화한 과거 수익률한다도 했는데 구체적인 수식과 파라미터 필요함. 앞으로도 구체적으로 답변.


---
$U_n$의 정의는 §1, 식 (1)입니다.

**기본 정의 (식 1)**

$$U_{n+1} = \frac{X_{n+1} - X_n}{\hat{\sigma}_n}, \qquad \hat{\sigma}_n = \mathbb{E}_n\big[(X_{n+1}-X_n)^2\big]^{1/2}$$

구성 요소를 하나씩:

- $X_n$ = 시점 $n$의 가격. Martin은 §1에서 **절대 변화** $X_{n+1}-X_n$를 기본 정의로 채택합니다(이후 모든 대수 전개에 사용). 상대 변화 $(X_{n+1}-X_n)/X_n \approx \Delta\ln X$도 언급하지만, 금리스왑처럼 가격이 음수가 될 수 있는 자산(2020년 4월 WTI 음수 사건 각주16) 때문에 절대 변화를 씁니다. 이론 전개에는 어느 쪽을 쓰든 critical하지 않다고 명시.

- $\hat{\sigma}_n$ = 시점 $n$까지의 정보 $\mathcal{F}_n$로 추정한, 다음 1기간 가격 변화의 **조건부 표준편차**. $\mathbb{E}_n[\cdot]$의 아래첨자 $n$이 "n까지 알려진 정보에 조건부"라는 뜻 — 즉 **look-ahead 금지**($\hat\sigma_n \in \mathcal{F}_n$).

- $U_{n+1}$ = "단위 변동성당 수익률(return per unit volatility)" = **risk-adjusted return** (각주4). $\hat\sigma_n$로 나누는 이유는 $U_n$을 **무차원·단위분산**으로 정규화하기 위함입니다.

**$\hat\sigma_n$의 구체적 추정식 (§2.5 실증)**

식 (1)의 $\hat\sigma_n$은 정의상 조건부 기댓값일 뿐, 실제 추정 방법은 §2.5(p.11)에서 못박습니다:

> "For risk-adjusting the returns we use a **20-day EMA of squared price changes** to estimate the volatility ($\hat\sigma_n$ in the definition of $U_n$)."

즉 분산 추정은 제곱 가격변화의 EMA:

$$\hat{\sigma}_n^2 = (1-\gamma)\sum_{i=0}^{\infty}\gamma^{i}(X_{n-i} - X_{n-1-i})^2$$

또는 재귀 형태로:

$$\hat{\sigma}_n^2 = \gamma\,\hat{\sigma}_{n-1}^2 + (1-\gamma)(X_n - X_{n-1})^2$$

**파라미터 $\gamma$**: "20-day EMA"이므로 effective period $N_\sigma = 20$. EMA 관례상 $\gamma = 1 - N_\sigma^{-1} = 1 - 1/20 = 0.95$. (Martin이 §2.1에서 쓰는 $\alpha = 1 - N^{-1}$ 매핑과 동일.)

**$U_n$에 대한 가정 (대수 전개의 전제)**

Martin은 이론 유도(§2.3 이후) 내내 다음을 가정합니다 (p.5–6):

1. **i.i.d.**: $U_n$들이 독립동일분포.
2. **평균 0**: $\mathbb{E}[U_n] = 0$. → 전략이 기대수익을 *내지 않는* 상황을 분석. (Potters & Bouchaud와 동일한 가정.)
3. **3차 moment 0**: 첫 세 moment가 $(0, 1, 0)$. 즉 분산 1, 왜도 0.

핵심: $U_n$ 자체는 **대칭(왜도 0)**으로 가정하는데도 거래 수익 $Y^{(M)}$의 왜도가 양수로 나온다 — 이게 §2 전체의 논점입니다.

**중요한 미묘점 — 각주6**

원시 수익률(raw returns)은 i.i.d.일 필요가 없습니다. **stochastic volatility** 때문에 raw return은 시변 분산을 갖지만, $\hat\sigma_n$으로 나눠주면 그 변동성 효과가 제거되어 $U_n$이 i.i.d. 가정에 가까워집니다. 이것이 vol-normalization의 또 다른 존재 이유입니다(무차원화 + i.i.d. 근사화).

**§4 nonlinear에서의 재정규화 차이**

§4(nonlinear)에서는 momentum factor $V_n = \sum_j a_j U_{n-j}$에 대해 **$R_0^a = 1$ (단위 분산)**이 되도록 $a_j$를 추가 스케일링합니다(p.17). 그 결과 EMA1은 $a_j = (1-\alpha^2)^{1/2}\alpha^j$, $R_k^a = \alpha^k$ 형태가 됩니다. §2(linear)와는 스케일 인자만 다를 뿐 본질은 동일.

**실무 적용 시 (당신의 검증 맥락)**

Martin fidelity를 맞추려면:

| 항목 | Martin 값 |
|---|---|
| return 정의 | 절대 변화 $X_{n+1}-X_n$ |
| vol estimator | 20-day EMA of squared price changes ($\gamma=0.95$) |
| $U_n$ 정규화 | $(X_{n+1}-X_n)/\hat\sigma_n$, 단위분산 무차원 |
| 가정 | $U_n$ i.i.d., moments $(0,1,0)$ |

당신의 Carver 엔진은 보통 (a) **percentage return**을 쓰고 (b) vol estimator가 36-day blend 또는 다른 lookback이라 — 이 두 가지가 Martin과 어긋나는 지점입니다. Theory 트랙에서 폐형식(식 17/19)과 직접 대조하려면 vol estimator를 **20-day EMA-of-squares($\gamma=0.95$)로, return을 절대 변화로** 맞추는 것이 정합적입니다. percentage return을 유지하려면 §1의 단서("상대 변화도 가능, 단 가격이 양수일 때만, 이론 전개에 critical하지 않음")에 기대 정당화할 수 있지만, 그 경우 fidelity 주장 시 각주로 명시하세요.


---
Un 즉 식(1)이 샤프비율과 다른 점은?



---
핵심 차이: **$U_n$은 단일 기간의 실현(realized) 수익률을 사전(ex-ante) 변동성 추정치로 나눈 확률변수**이고, **Sharpe ratio는 그 분포의 두 모수(평균·표준편차)의 비율인 상수(스칼라)**입니다. 하나는 매 시점 새로 나오는 *난수*, 하나는 분포 전체를 요약하는 *통계량*입니다.

식으로 대비하면 명확합니다.

**$U_n$ (식 1):**
$$U_{n+1} = \frac{X_{n+1}-X_n}{\hat{\sigma}_n}, \qquad \hat{\sigma}_n = \mathbb{E}_n[(X_{n+1}-X_n)^2]^{1/2}$$

**Sharpe ratio** (논문에서 $\mathfrak{r}$로 표기, §2.5 p.13):
$$\mathfrak{r} = \frac{\kappa_1}{\kappa_2^{1/2}} = \frac{\mathbb{E}[R]}{\text{sd}(R)}$$

차이를 항목별로:

| 항목 | $U_n$ (식 1) | Sharpe ratio $\mathfrak{r}$ |
|---|---|---|
| **수학적 대상** | 확률변수 (random variable), 시점마다 값이 다름 | 스칼라 상수 (분포의 요약) |
| **분자** | 단일 기간 *실현* 수익률 $X_{n+1}-X_n$ | 수익률의 *기댓값* $\mathbb{E}[R]=\kappa_1$ |
| **분모** | *조건부·사전* 변동성 추정 $\hat\sigma_n$ ($\mathcal{F}_n$ 기반, 그 시점까지 정보로 추정) | 수익률의 *무조건·사후* 표준편차 $\kappa_2^{1/2}$ (전체 표본의 실현 변동성) |
| **시점성** | 분모가 시변 ($\hat\sigma_n$이 매일 갱신) | 분모가 표본 전체에 대한 단일 값 |
| **평균** | 가정상 $\mathbb{E}[U_n]=0$ (식 1의 분자에 기댓값을 빼지 않음) | 분자가 곧 평균이므로 평균이 핵심 |

**가장 본질적인 두 차이**

1. **분자: 실현값 vs 기댓값.** $U_n$의 분자는 그날 실제로 일어난 가격변화입니다(평균을 빼지 않음 — Martin은 $\mathbb{E}[U_n]=0$을 *가정*할 뿐 정의에서 차감하지 않음). Sharpe의 분자는 평균 $\mathbb{E}[R]$ 그 자체. 그래서 $U_n$은 시점마다 +든 −든 흩어지지만, Sharpe의 분자는 분포가 어느 쪽으로 기울었는지를 하나의 수로 답합니다.

2. **분모: 조건부 사전추정 vs 무조건 사후표준편차.** $\hat\sigma_n$은 $\mathcal{F}_n$에 속하는, *그 시점까지의 정보로 만든 예측치*입니다(look-ahead 금지). Sharpe의 $\kappa_2^{1/2}$는 표본 전체를 보고 계산한 사후 통계량입니다. 전자는 "내일 변동성을 오늘 추정"이고, 후자는 "전 기간을 다 본 뒤 계산"입니다.

**둘이 닮아 보이는 이유와, 그 연결고리**

구조가 (수익률)/(변동성)으로 같아서 헷갈립니다. 실제로 연결됩니다 — 각주5(p.4):

> 무차원 신호 $S$가 risk-adjusted return $\mu/\sigma$를 대표하면, 최적 포지션은 $S/\sigma$.

여기서 $\mu/\sigma$가 바로 **(연속시간) Sharpe ratio의 모집단 버전**입니다. 즉 $U_n$은 **단일 기간 표본에서의 risk-adjusted return**이고, 이것을 *모집단 차원에서 기대값으로 본 것*이 Sharpe입니다. 거칠게 말하면:

$$\mathbb{E}[U_n] \;\approx\; \text{(1기간) Sharpe ratio의 모집단 값}$$

그런데 Martin은 이론 전개에서 의도적으로 $\mathbb{E}[U_n]=0$으로 둡니다 → **"전략이 기대수익을 내지 않는(=Sharpe 0인) 상황에서도 거래수익 왜도가 양수"**임을 보이기 위해서입니다. 즉 $U_n$의 평균(≈Sharpe)을 0으로 죽여놓고 왜도만 살아남는 걸 증명하는 구조.

**한 가지 더 — 적용 대상이 다름**

- $U_n$은 **시장(underlying)의** risk-adjusted return입니다.
- Sharpe $\mathfrak{r}$는 §2.5에서 **거래 전략(trading return $Y^{(M)}$)의** 성과 지표로 등장합니다.

§2.5의 실증에서 이 구분이 핵심으로 쓰입니다: 100–200일 구간에서 거래수익의 Sharpe ≈ +0.2, 왜도 ≈ 2 → Gram-Charlier로 "수익이 0을 넘을 확률"을 계산하면 약 0.45(절반 미만). 즉 **이기는 거래 비율은 절반 이하인데도 양의 Sharpe** — 양의 왜도가 만드는 trend-following의 특징입니다. 여기서 $U_n$(시장 수준 입력)과 Sharpe(전략 성과 출력)가 완전히 다른 층위임이 드러납니다.

---

요약: **$U_n$ = 시장의 한 기간 실현수익을 사전·조건부 변동성으로 나눈 난수**, **Sharpe = 수익률 분포의 평균/표준편차라는 스칼라 요약통계**. 구조는 닮았지만 $U_n$은 매 시점의 입력 확률변수, Sharpe는 분포(주로 전략 수익)의 출력 지표이며, Martin은 $\mathbb{E}[U_n]=0$(=Sharpe 0)으로 설정해 "성과 없이도 왜도는 생긴다"를 증명합니다.



---
Martin 이 조건부 사전추정을 한 방법은?




---
Martin이 $\hat\sigma_n$(조건부·사전 변동성)을 추정한 구체적 방법은 §2.5(p.11)에 단 한 줄로 명시됩니다:

> "For risk-adjusting the returns we use a **20-day EMA of squared price changes** to estimate the volatility ($\hat\sigma_n$ in the definition of $U_n$)."

즉 **제곱 가격변화(squared price changes)의 20일 지수가중이동평균(EMA)**입니다. 이것이 식 (1)의 조건부 기댓값 $\hat\sigma_n = \mathbb{E}_n[(X_{n+1}-X_n)^2]^{1/2}$를 실제로 구현한 estimator입니다.

**구현 형태**

분산 추정 (재귀):
$$\hat{\sigma}_n^2 = \gamma\,\hat{\sigma}_{n-1}^2 + (1-\gamma)(X_n - X_{n-1})^2$$

또는 동치인 무한합:
$$\hat{\sigma}_n^2 = (1-\gamma)\sum_{i=0}^{\infty}\gamma^{i}\,(X_{n-i}-X_{n-1-i})^2$$

그리고 $\hat\sigma_n = \sqrt{\hat\sigma_n^2}$.

**파라미터**
- effective period $N_\sigma = 20$ (논문이 "20-day"로 명시).
- decay $\gamma = 1 - N_\sigma^{-1} = 1 - 1/20 = 0.95$ (§2.1의 $\alpha = 1-N^{-1}$ 매핑 적용).

**왜 이 방법이 "조건부·사전(ex-ante)"을 만족하는가 — 세 가지 포인트**

1. **인과성(causality) / look-ahead 금지.** EMA는 $X_n, X_{n-1}, \dots$ 즉 **시점 $n$까지의 과거 가격변화만** 사용합니다. 미래 정보가 안 들어가므로 $\hat\sigma_n \in \mathcal{F}_n$ (식 1과 §1의 "$\varphi_n \in \mathcal{F}_n$, otherwise the strategy can cheat by looking ahead" 요건 충족). 이 점이 "사전(ex-ante)"의 핵심입니다 — 그날의 변동성을 그날까지의 정보로 예측.

2. **제곱변화의 기댓값 = 조건부 분산.** $\mathbb{E}_n[(X_{n+1}-X_n)^2]$를 추정하는 가장 단순한 인과적 estimator가 과거 제곱변화의 가중평균이고, EMA는 그 가중을 지수적으로(최근일수록 무겁게) 준 것입니다. 즉 정의식의 조건부 2차 moment를 "최근 제곱변화에 큰 비중"으로 근사.

3. **절대 변화 사용.** 분자가 $(X_n - X_{n-1})$ — 즉 §1에서 채택한 **절대 가격변화**의 제곱입니다. percentage return의 제곱이 아닙니다. (음수 가격 자산 호환 위해 절대 변화 채택한 §1 결정과 일관.)

**EMA를 택한 이유 (논문의 일관된 논리)**

§2.1에서 Martin은 moving-average filter로 EMA를 선호하는 이유를 밝힙니다 — "easily calculated by recursion." 모델 기반 필터(Bruder, Jusselin 등)보다 **편의적 정의를 쓰고 그 위에서 전략을 설계**하는 것이 낫다는 입장(p.2). 변동성 추정도 같은 철학으로 EMA를 씁니다: 모델을 가정하지 않고, 재귀로 싸게 계산되며, 인과적인 추정기.

**중요한 함의 — stochastic volatility 제거 (각주6)**

이 $\hat\sigma_n$ 나눗셈이 단순 정규화가 아닙니다. raw return은 시변 변동성 때문에 i.i.d.가 아니지만, **각 시점의 조건부 변동성 추정치로 나눠주면** 그 변동성 구조가 제거되어 $U_n$이 §2.3 이론의 전제인 **i.i.d.·단위분산** 가정에 근접합니다(각주6: "the raw returns need not be, because of stochastic volatility, which is another reason for dividing off by an estimate of the stdev"). 즉 20-day EMA vol scaling은 *이론 가정을 실데이터에서 성립시키기 위한 장치*이기도 합니다.

**§2.5 실증 셋업에서의 위치**

전체 risk-adjusting 파이프라인:
| 단계 | 내용 |
|---|---|
| 가격변화 | $X_n - X_{n-1}$ (절대 변화) |
| 변동성 추정 | 20-day EMA of $(X_n-X_{n-1})^2$, $\gamma=0.95$ |
| 정규화 | $U_n = (X_n-X_{n-1})/\hat\sigma_{n-1}$ |
| 그 위의 momentum | EMA2 with $N=20,40$ (CHFUSD·SPX futures, 1990–2009) |

**주의 — 논문이 명시하지 않는 디테일**

Martin은 "20-day EMA of squared price changes"만 말하고, 다음은 명시하지 않습니다:
- **mean 차감 여부**: 제곱변화를 그대로 쓰는지($\mathbb{E}[\Delta X]\approx 0$ 가정), 아니면 변화에서 평균을 뺀 뒤 제곱하는지. 문맥상 평균≈0 가정하에 **raw 제곱변화**를 쓰는 것으로 읽힙니다(§2.3의 zero-mean 가정과 일관).
- **초기화(seeding)**: $\hat\sigma_0$를 무엇으로 시작하는지.
- **시차(lag) 정확한 인덱싱**: $U_{n+1}$의 분모가 $\hat\sigma_n$인지 $\hat\sigma_{n-1}$인지는 식 (1)이 $\hat\sigma_n$으로 명시(시점 $n$의 정보로 $n\to n+1$ 변화를 정규화).

검증 시 이 세 가지는 직접 정해야 하며, fidelity 주장에 영향을 줄 수 있으니 evidence pack에 가정으로 박아두는 게 안전합니다.



---
Martin 논문과 carver 엔진의 차이를 비교 테이블로 작성. 목적은 이 둘간의 차이가 Martin 논문의 결과에  얼마나 크게 영향을 미치는 팩터인지를 알아보고 하는 것임.




---
Carver 엔진의 정확한 구현 세부(특히 당신의 ARS 설정에 들어간 lookback·blend·buffer 파라미터)는 버전·설정마다 다르므로, 아래는 **Carver의 공개된 표준 사양**(*Systematic Trading* / *Advanced Futures Trading Strategies*)을 기준으로 작성했습니다. 당신 엔진의 실제 값과 다르면 알려주세요 — 영향도 평가가 바뀝니다.

## 비교 테이블: Martin (2021) vs Carver 표준 엔진

| # | 항목 | Martin 논문 | Carver 표준 엔진 | Martin 결과 영향도 | 영향 방향·메커니즘 |
|---|---|---|---|---|---|
| 1 | **Return 정의** | 절대 가격변화 $X_{n+1}-X_n$ | percentage / price return | **낮음** | §1 명시: 이론 전개에 critical하지 않음. 단 vol-normalize 후엔 거의 동일해짐. fidelity 각주만 필요 |
| 2 | **Vol estimator** | 20-day EMA of squared price changes ($\gamma{=}0.95$) | 32-day EMA(또는 35d) blend, 가끔 long-run vol과 혼합 | **중간** | term structure의 **수평 스케일**만 이동(peak 위치). 형상·peak 높이는 보존. §4.3: "faster/slower vol → graph를 수평으로 stretch/compress" |
| 3 | **포지션 함수 $\psi$** | linear ($\psi(z){=}z$) | **forecast cap ±20** (clip) | **높음** | §4.2.1 simple sigmoid와 동형. capping → term structure **수직 압축**, peak 2.1→하락. linear 폐형식(식 17/19) 직접 비교 불가 |
| 4 | **포지션 양자화** | 연속 (continuous $\varphi_n$) | **integer contracts** | **매우 높음** | §4.2.3 double-step 영역. $\epsilon{\to}0$=binary sgn → **왜도 소멸**. $50k$+single+full-size면 {0,1,2} 계단화로 Martin 효과 파괴 가능. **최대 confound** |
| 5 | **Buffering** | 없음 | position buffer (no-trade zone) | **중간** | 추가 경로의존 + 거래 억제. §4.4의 "discontinuous model이 simulated position을 크게 바꾼다"는 경고에 해당. roundtrip 정의에도 영향 |
| 6 | **속도 구조** | single EMA2 (폐형식 분석) | **6-speed EWMAC 합성** (equal weight) | **중간** | 모든 $a_j{>}0$이라 **양의 왜도 정성결과는 보존**(식 12). 단 peak 위치/높이의 single-speed 폐형식(식 17/19)과 **직접 대조 불가** |
| 7 | **EMA1 vs EMA2** | 둘 다 분석, EMA2 선호(path-length) | EWMAC = fast−slow = **EMA2 계열** | **낮음** | 일치. Carver EWMAC가 곧 Martin EMA2. 정합적 |
| 8 | **Forecast scaling** | 없음 (raw $V_n$) | forecast scalar(목표 abs≈10) + vol target 20% | **낮음** | 선형 스케일 → 왜도는 scale-invariant. 왜도값 자체엔 무영향 |
| 9 | **$U_n$ 가정** | i.i.d., moments $(0,1,0)$, $\mathbb{E}[U]{=}0$ | 실데이터 (drift≠0, fat tail, vol clustering) | **중간** | §2.5가 이미 인정한 괴리. drift>0 → 단기 왜도 음수 쪽 편향(식 type-iv 항). central/non-central skew 분리로 부분 보정 |
| 10 | **거래비용** | 무시 (path-length로 정성 논의만) | 실제 cost model 반영 | **낮음(왜도)/중간(SR)** | 왜도 자체엔 거의 무영향. SR 비교에는 영향 |
| 11 | **Carry rule** | 없음 (pure momentum) | 보통 포함 (당신은 OFF) | **해당없음** | OFF로 통제됨 → 정합 |
| 12 | **데이터 범위** | single instrument, 20y+ (1990–2009) | multi-instrument 가능 (당신은 single) | **낮음** | single로 맞추면 §2.5와 동일 셋업 |

## 영향도 종합 — Martin 결과를 깨는 순서

**왜도 term structure 형상을 직접 위협하는 팩터** (이론 검증의 적):

1. **Integer quantization (#4) — 압도적 1순위.** 다른 모든 걸 맞춰도 이것 하나로 binary-step regime에 빠지면 Martin이 *명시적으로 왜도가 사라진다*고 한 영역이 됩니다. $50k$ single-instrument full-size면 거의 확실히 문제. → **micro contracts 필수** 또는 capital 확대.

2. **Forecast cap ±20 (#3) — 2순위.** sigmoid capping과 동형이라 peak를 깎습니다. 다만 §4.2.1 결과와 *일관*되므로 "linear가 아닌 capped sigmoid baseline"으로 재명명하면 검증 자체는 성립. linear 폐형식과 대조하려면 **cap OFF 트랙 별도 필요**.

3. **6-speed 합성 (#6) — 정성 OK, 폐형식 NO.** 양의 왜도 *존재*는 검증되지만 peak≈2.1·$M\approx1.7(N_\alpha+N_\beta)$ 같은 *수치* 검증엔 부적합.

**형상은 보존하되 축을 이동시키는 팩터** (해석만 조정하면 됨):

4. **Vol estimator (#2)**, **drift (#9)** — peak를 수평/약간 수직 이동. §2.5·§4.3가 이미 다룬 known deviation.

**거의 무해한 팩터** (각주 처리):

5. Return 정의(#1), forecast scaling(#8), 거래비용(#4→왜도 측면), EMA2 매칭(#7).

## 검증 설계로의 직접 함의

이 테이블이 앞서 권고한 **2-트랙 분리**의 근거입니다:

| 트랙 | 통제해야 할 팩터 | 검증 가능한 Martin 클레임 |
|---|---|---|
| **Theory** | #2→20d EMA, #3→cap OFF, #4→continuous, #6→single-speed EMA2, #1→절대변화 | 식 17/19 폐형식 (peak값·$M^{-1/2}$·위치) |
| **Realistic** | 현 spec 유지 (#3,4,5,6 포함, micro만 강제) | 정성 3대 주장: ① 양의 왜도 존재, ② term structure 형상, ③ sizing 기원($U_n$ vs trading-return 왜도 대비) |

**한 줄 결론**: Martin 결과를 망치는 단 하나의 결정적 팩터는 **#4 integer quantization**이고(→micro 필수), 그 다음이 **#3 forecast cap**(→linear 검증엔 cap OFF). 나머지(#2·#6·#9)는 *형상은 보존하되 축을 옮기는* 알려진 편차라 해석 조정으로 흡수 가능합니다. #1·#7·#8·#11은 사실상 무시 가능.

검증 우선순위를 정하시려면, 현재 ARS 엔진의 **실제 vol lookback·forecast cap 유무·micro 사용 여부** 세 가지만 확인해 주시면 이 표의 영향도를 당신 셋업에 맞춰 재계산하겠습니다.


