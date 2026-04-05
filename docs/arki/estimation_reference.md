# pysystemtrade Estimation Flags — Code-Based Reference

> Each flag switches between a **fixed value from config** and a **data-driven estimation**.
> This document traces each mechanism to the actual code.

---

## 1. Forecast Scalar (`use_forecast_scale_estimates`)

### What is it?
Raw forecast 값을 적절한 크기로 스케일링하는 배수. 목표: 스케일링 후 forecast의 **평균 절대값 = 10**.

### Fixed mode (Production: `False`)
```yaml
# arki_production.yaml
forecast_scalars:
  momentum4: 8.54    # EWMAC(4,16)의 raw output에 8.54를 곱함
  momentum8: 5.95
  carry30: 28.38     # Carry의 raw output은 매우 작으므로 큰 scalar 필요
  relmomentum20: 86.51  # CS Momentum raw output이 가장 작음 → 가장 큰 scalar
```
이 값들은 Rob Carver가 책에서 계산한 고정값.

### Estimated mode (v5a: `True`)
**Code**: `sysquant/estimators/forecast_scalar.py` line 8-50

```python
def forecast_scalar(cs_forecasts, target_abs_forecast=10.0, window=250000, ...):
    # 1. 모든 종목의 raw forecast를 cross-sectionally pool
    x = cs_forecasts.ffill().abs().median(axis=1)  # 종목 간 중앙값
    
    # 2. Rolling window으로 평균 절대값 계산
    avg_abs_value = x.rolling(window=window, min_periods=500).mean()
    
    # 3. 목표(10) / 실측 = scalar
    scaling_factor = target_abs_forecast / avg_abs_value
```

**핵심**: "이 규칙의 raw output 평균 절대값이 얼마인지" 데이터로 측정해서 10으로 맞춰줌.
- Expanding window (window=250,000 = 사실상 전체 기간)
- 종목 간 pool → scalar는 **규칙당 하나** (모든 종목 동일)
- min_periods=500일 → 약 2년 데이터 필요

### 왜 중요한가?
Scalar가 너무 크면 forecast가 자주 ±20 cap에 닿아 포지션이 항상 최대치. 너무 작으면 forecast가 0 근처에서 놀아 포지션이 거의 없음. **올바른 크기 설정이 position sizing의 전제조건**.

### Production vs v5a의 차이
| | Production | v5a |
|---|---|---|
| Carry30 scalar | **고정 28.38** | 데이터가 알아서 (시간에 따라 변할 수 있음) |
| 리스크 | 오래된 값이면 현재 시장과 안 맞을 수 있음 | 시장 변화에 적응 |
| 과적합 | 없음 | 거의 없음 (window가 매우 큼) |

---

## 2. Forecast Weights (`use_forecast_weight_estimates`)

### What is it?
11개 trading rule의 가중치. "Trend에 33%, Carry에 33%, CS Mom에 33%"를 결정하는 것.

### Fixed mode (v5a: 고정 35/20/45)
```yaml
forecast_weights:
  momentum4: 0.070     # 35% / 5 rules
  carry30: 0.067       # 20% / 3 rules
  relmomentum20: 0.150 # 45% / 3 rules
```

### Estimated mode (Production: `True`)
**Code**: `systems/forecast_combine.py` line 600-633

```python
def get_raw_estimated_forecast_weights(self, instrument_code):
    weighting_func = resolve_function(weighting_params.pop("func"))
    # func = sysquant.optimisation.generic_optimiser.genericOptimiser
    
    returns_pre_processor = self.returns_pre_processor_for_code(instrument_code)
    weight_func = weighting_func(returns_pre_processor, ...)
    # → 내부적으로 Handcraft 알고리즘 사용 (종목 수준과 동일)
```

**동작 방식**: 
1. 각 trading rule의 과거 수익률을 계산
2. Rule 간 상관관계 행렬 추정
3. Handcraft 알고리즘으로 최적 가중치 추정
4. **비용 필터**: SR cost가 ceiling보다 높은 rule은 자동 제외
5. 종목 간 pooling (같은 set의 rule을 가진 종목들을 합쳐서 추정)

### 왜 중요한가?
Carry가 최근 3년 SR=-0.20이면, 시스템이 자동으로 carry 비중을 줄임. **팩터 로테이션이 자동화**됨.

### ⚠️ Production vs v5a에서의 아이러니
| | Production | v5a |
|---|---|---|
| Forecast weights | **시스템 추정** (Handcraft) | **인간 고정** (35/20/45) |

**Production이 이미 더 "시스템적"입니다.** v5a에서 인간이 개입한 유일한 곳.

---

## 3. Forecast Diversification Multiplier (`use_forecast_div_mult_estimates`)

### What is it?
여러 rule을 결합할 때의 **분산 효과 보정 계수**. 예: 3개 rule이 약간 상관되면, 결합 후 forecast가 줄어듦 → FDM으로 복원.

### Fixed mode (v5a: 고정 1.35)
```yaml
forecast_div_multiplier: 1.35
```
Combined forecast에 1.35를 곱함 → forecast 크기가 35% 증가.

### Estimated mode (Production: `True`)
**Code**: `systems/forecast_combine.py` line 1100-1164

```python
def get_forecast_diversification_multiplier_estimated(self, instrument_code):
    correlation_list = self.get_forecast_correlation_matrices(instrument_code)
    weight_df = self.get_forecast_weights(instrument_code)
    
    # FDM = 1 / sqrt(w' × Corr × w)
    ts_fdm = idm_func(correlation_list, weight_df, **div_mult_params)
```

**동작**: Rule 간 상관관계가 낮을수록 FDM이 높아짐 → forecast가 증폭 → 더 큰 포지션 → 분산 효과를 최대한 활용.

### 왜 중요한가?
고정 FDM(1.35)은 rule 간 상관관계가 변해도 못 따라감. 시장 위기 시 모든 trend rule 상관관계가 1에 수렴하면, 고정 FDM은 포지션을 과대평가.

---

## 4. Instrument Diversification Multiplier (`use_instrument_div_mult_estimates`)

### What is it?
FDM과 같은 개념이지만 **종목 수준**. 25개 종목을 결합할 때의 분산 효과.

### Both Production & v5a: `True` (동일)
**Code**: `systems/portfolio.py` line 288-330

```python
def get_estimated_instrument_diversification_multiplier(self):
    correlation_list = self.get_instrument_correlation_matrix()
    weight_df = self.get_instrument_weights()
    ts_idm = idm_func(correlation_list, weight_df, ...)
    # IDM = 1 / sqrt(w' × Corr × w)
```

### 왜 중요한가?
25개 종목 간 상관관계가 전반적으로 낮으면 IDM이 ~2.5까지 올라가 포지션을 2.5배로 키움.
이것은 분산투자의 "공짜 점심"을 수학적으로 계산한 것.

---

## 5. Risk Overlay

### What is it?
포트폴리오 risk가 과도해지면 **모든 포지션을 일괄 축소**하는 안전장치.

### Production 설정
```yaml
risk_overlay:
  max_risk_fraction_normal_risk: 2.0    # 목표 risk의 2배 초과 시 축소
  max_risk_fraction_stdev_risk: 4.0     # Vol shock 시 4배까지 허용
  max_risk_limit_sum_abs_risk: 5.0      # 총 |exposure| 5배 limit
  max_risk_leverage: 15.0               # 레버리지 15배 초과 금지
```

### v5a: **없음** (defaults에서도 주석처리)
→ 극단적 시장에서 무제한 레버리지 가능. **위험**.

### Code: `systems/portfolio.py` line 948-966
```python
def get_risk_scalar(self):
    risk_scalar = get_risk_multiplier(
        normal_risk=...,      # 현재 포트폴리오 vol
        shocked_vol_risk=..., # vol × 2로 stress test
        sum_abs_risk=...,     # 총 절대 risk
        leverage=...,         # 현재 레버리지
    )
    # 반환: 0.0~1.0 사이 스칼라. 모든 포지션에 곱해짐.
```

---

## 6. Small System / Shadow Cost

### What is it?
Dynamic optimization(Mr. Greedy)에서 **거래 비용 패널티**를 조절.

### Production 설정
```yaml
small_system:
  shadow_cost: 10                          # 거래 비용을 10배로 뻥튀기
  tracking_error_buffer: 0.12              # 추적 오차 12% 허용
  cost_multiplier: 1.0                     # 실제 비용 승수
  shrink_instrument_returns_correlation: 0.5  # 상관관계 shrinkage
```

### v5a: **없음** → defaults의 `shadow_cost: 50`
→ **v5a가 5배 보수적** (shadow_cost 50 vs 10). 거래를 훨씬 덜 함.

### 왜 중요한가?
Shadow cost가 낮으면(10): 작은 신호 변화에도 거래 → 높은 turnover → 더 정확한 추종
Shadow cost가 높으면(50): 큰 신호 변화만 거래 → 낮은 turnover → 비용 절약

---

## 7. Volatility Calculation

### Production 설정
```yaml
volatility_calculation:
  func: sysquant.estimators.vol.mixed_vol_calc
  days: 35                      # 단기 vol: 35일 
  slow_vol_years: 20            # 장기 vol: 20년
  proportion_of_slow_vol: 0.35  # 최종 = 65% 단기 + 35% 장기
  backfill: true
```

### v5a: **없음** → system defaults
| | Production | v5a (default) |
|---|---|---|
| days | 35 | 35 |
| proportion_of_slow_vol | 0.35 | 0.30 |

미세한 차이. 장기 vol 비중이 35% vs 30%.

---

## 종합: Production을 v5a로 전환하려면?

**최소한의 변경** — Production config에서 1줄만 수정:
```yaml
use_instrument_weight_estimates: True   # False → True
```

나머지는 그대로 두는 것이 **더 안전**:
- Forecast weights: 이미 시스템 추정 중 ✅
- Forecast scalars: 고정값이 더 안정적 (Carver 원저자 계산) ✅
- Risk overlay: 반드시 유지 ✅
- Small system: shadow_cost 10이 현재 계좌에 적합 ✅
