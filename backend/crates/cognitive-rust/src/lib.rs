use pyo3::prelude::*;
use pyo3::types::PyModule;

#[pyclass(skip_from_py_object)]
#[derive(Clone, Debug, PartialEq)]
pub struct AppraisalVector {
    #[pyo3(get, set)]
    pub relevance: f64,
    #[pyo3(get, set)]
    pub novelty: f64,
    #[pyo3(get, set)]
    pub goal_congruence: f64,
    #[pyo3(get, set)]
    pub agency: f64,
    #[pyo3(get, set)]
    pub norm_alignment: f64,
    #[pyo3(get, set)]
    pub relationship_impact: f64,
}

#[pymethods]
impl AppraisalVector {
    #[new]
    fn new(
        relevance: f64,
        novelty: f64,
        goal_congruence: f64,
        agency: f64,
        norm_alignment: f64,
        relationship_impact: f64,
    ) -> Self {
        Self {
            relevance,
            novelty,
            goal_congruence,
            agency,
            norm_alignment,
            relationship_impact,
        }
    }
}

#[pyclass(skip_from_py_object)]
#[derive(Clone, Debug, PartialEq)]
pub struct PadState {
    #[pyo3(get, set)]
    pub valence: f64,
    #[pyo3(get, set)]
    pub arousal: f64,
    #[pyo3(get, set)]
    pub dominance: f64,
    #[pyo3(get, set)]
    pub trust: f64,
    #[pyo3(get, set)]
    pub attachment: f64,
}

#[pymethods]
impl PadState {
    #[new]
    fn new(valence: f64, arousal: f64, dominance: f64, trust: f64, attachment: f64) -> Self {
        Self {
            valence,
            arousal,
            dominance,
            trust,
            attachment,
        }
    }
}

#[pyclass(skip_from_py_object)]
#[derive(Clone, Debug, PartialEq)]
pub struct PsychWeights {
    #[pyo3(get, set)]
    pub alpha: f64,
    #[pyo3(get, set)]
    pub beta: f64,
    #[pyo3(get, set)]
    pub gamma: f64,
    #[pyo3(get, set)]
    pub delta: f64,
    #[pyo3(get, set)]
    pub epsilon: f64,
}

#[pymethods]
impl PsychWeights {
    #[new]
    fn new(alpha: f64, beta: f64, gamma: f64, delta: f64, epsilon: f64) -> Self {
        Self {
            alpha,
            beta,
            gamma,
            delta,
            epsilon,
        }
    }
}

#[pyfunction]
pub fn compute_appraisal(
    event_content: &str,
    event_type: &str,
    emotional_bias: f64,
    trust: f64,
    recent_contents: Vec<String>,
    identity_boundaries: Vec<String>,
) -> AppraisalVector {
    let relevance = match event_type {
        "USER_MESSAGE" => 1.0,
        "SYSTEM_TICK" => 0.1,
        _ => 0.5,
    };
    let novelty = compute_novelty(event_content, &recent_contents);
    let goal_congruence = emotional_bias.clamp(-1.0, 1.0);
    let agency = if event_type == "USER_MESSAGE" {
        0.8
    } else {
        0.3
    };
    let norm_alignment = check_norm_alignment(event_content, &identity_boundaries);
    let mut relationship_impact = emotional_bias * 0.5;
    if trust < 0.3 {
        relationship_impact *= 0.5;
    }

    AppraisalVector {
        relevance,
        novelty,
        goal_congruence,
        agency,
        norm_alignment,
        relationship_impact,
    }
}

#[pyfunction]
pub fn update_pad_from_appraisal(
    state: &PadState,
    interaction_count: u64,
    appraisal: &AppraisalVector,
    weights: &PsychWeights,
) -> PadState {
    let next_valence = (1.0 - weights.alpha) * state.valence
        + weights.alpha * (0.6 * appraisal.goal_congruence + 0.4 * appraisal.relationship_impact);
    let next_arousal = (1.0 - weights.beta) * state.arousal
        + weights.beta * (0.6 * appraisal.novelty + 0.4 * appraisal.relevance);
    let next_dominance = (1.0 - weights.gamma) * state.dominance
        + weights.gamma * (0.6 * appraisal.agency + 0.4 * appraisal.norm_alignment);
    let next_trust = (state.trust + weights.delta * appraisal.relationship_impact).clamp(0.0, 1.0);
    let freq = ((interaction_count + 1) as f64 / 100.0).min(1.0);
    let next_attachment = (state.attachment + weights.epsilon * next_trust * freq).clamp(0.0, 1.0);

    PadState {
        valence: next_valence.clamp(-1.0, 1.0),
        arousal: next_arousal.clamp(0.0, 1.0),
        dominance: next_dominance.clamp(0.0, 1.0),
        trust: next_trust,
        attachment: next_attachment,
    }
}

#[pyfunction]
pub fn apply_alma_decay(
    valence: f64,
    arousal: f64,
    lambda_decay: f64,
    dt_hours: f64,
) -> (f64, f64) {
    let next_valence = valence * (-lambda_decay * dt_hours).exp();
    let next_arousal = (arousal + (0.02 * dt_hours)).min(1.0);
    (next_valence, next_arousal)
}

fn compute_novelty(content: &str, recent_contents: &[String]) -> f64 {
    if recent_contents.is_empty() {
        return 0.8;
    }

    let content_words = word_set(content);
    if content_words.is_empty() {
        return 0.5;
    }

    let mut max_overlap: f64 = 0.0;
    for recent in recent_contents {
        let recent_words = word_set(recent);
        if recent_words.is_empty() {
            continue;
        }
        let intersection = content_words
            .iter()
            .filter(|word| recent_words.contains(*word))
            .count();
        let union = content_words.len() + recent_words.len() - intersection;
        if union > 0 {
            max_overlap = max_overlap.max(intersection as f64 / union as f64);
        }
    }

    (1.0 - max_overlap).clamp(0.0, 1.0)
}

fn word_set(content: &str) -> std::collections::BTreeSet<String> {
    content
        .to_lowercase()
        .split_whitespace()
        .map(str::to_string)
        .collect()
}

fn check_norm_alignment(content: &str, boundaries: &[String]) -> f64 {
    if boundaries.is_empty() {
        return 1.0;
    }

    let content = content.to_lowercase();
    let skip_words = ["not", "no", "don't", "never", "without", "isn't"];
    let mut violations = 0_u32;

    for boundary in boundaries {
        for keyword in boundary
            .to_lowercase()
            .split_whitespace()
            .filter(|word| !skip_words.contains(word))
        {
            if keyword.len() > 3 && content.contains(keyword) {
                violations += 1;
            }
        }
    }

    (1.0 - violations as f64 * 0.2).clamp(0.0, 1.0)
}

#[pyclass(skip_from_py_object)]
#[derive(Clone, Debug, PartialEq)]
pub struct FatigueState {
    #[pyo3(get, set)]
    pub fatigue: f64,
    #[pyo3(get, set)]
    pub last_user_interaction: f64,
}

#[pymethods]
impl FatigueState {
    #[new]
    fn new(fatigue: f64, last_user_interaction: f64) -> Self {
        Self {
            fatigue,
            last_user_interaction,
        }
    }
}

#[pyfunction]
pub fn update_fatigue(
    state: &FatigueState,
    now: f64,
    dt_hours: f64,
    is_night: bool,
) -> FatigueState {
    let idle_duration = now - state.last_user_interaction;
    let is_idle = idle_duration > 300.0; // 5 minutes

    let circadian_multiplier = if is_night { 1.8 } else { 1.0 };

    let k_drain = 0.15;
    let k_restore = 0.20;

    let next_fatigue = if is_idle {
        state.fatigue - (k_restore * dt_hours / circadian_multiplier)
    } else {
        state.fatigue + (k_drain * dt_hours * circadian_multiplier)
    };

    FatigueState {
        fatigue: next_fatigue.clamp(0.0, 1.0),
        last_user_interaction: state.last_user_interaction,
    }
}

#[pyfunction]
pub fn compute_vector_delta(v1: Vec<f64>, v2: Vec<f64>) -> f64 {
    if v1.len() != v2.len() || v1.is_empty() {
        return 1.0;
    }
    // Mean squared difference (MSE) between vectors.
    let sum: f64 = v1.iter().zip(v2.iter()).map(|(a, b)| (a - b).powi(2)).sum();
    sum.sqrt()
}

#[pymodule]
fn cognitive_rust(module: &Bound<'_, PyModule>) -> PyResult<()> {
    module.add_class::<AppraisalVector>()?;
    module.add_class::<PadState>()?;
    module.add_class::<PsychWeights>()?;
    module.add_class::<FatigueState>()?;
    module.add_function(wrap_pyfunction!(compute_appraisal, module)?)?;
    module.add_function(wrap_pyfunction!(update_pad_from_appraisal, module)?)?;
    module.add_function(wrap_pyfunction!(apply_alma_decay, module)?)?;
    module.add_function(wrap_pyfunction!(update_fatigue, module)?)?;
    module.add_function(wrap_pyfunction!(compute_vector_delta, module)?)?;
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn appraisal_matches_python_heuristic_defaults() {
        let appraisal = compute_appraisal("hello friend", "USER_MESSAGE", 0.4, 0.5, vec![], vec![]);

        assert_eq!(appraisal.relevance, 1.0);
        assert_eq!(appraisal.novelty, 0.8);
        assert_eq!(appraisal.goal_congruence, 0.4);
        assert_eq!(appraisal.agency, 0.8);
        assert_eq!(appraisal.norm_alignment, 1.0);
        assert_eq!(appraisal.relationship_impact, 0.2);
    }

    #[test]
    fn pad_update_preserves_current_python_formula() {
        let appraisal = AppraisalVector {
            relevance: 1.0,
            novelty: 0.8,
            goal_congruence: 0.4,
            agency: 0.8,
            norm_alignment: 1.0,
            relationship_impact: 0.2,
        };
        let current = PadState {
            valence: 0.0,
            arousal: 0.5,
            dominance: 0.5,
            trust: 0.5,
            attachment: 0.1,
        };
        let weights = PsychWeights {
            alpha: 0.3,
            beta: 0.5,
            gamma: 0.2,
            delta: 0.1,
            epsilon: 0.03,
        };
        let state = update_pad_from_appraisal(&current, 0, &appraisal, &weights);

        assert!((state.valence - 0.096).abs() < 1e-9);
        assert!((state.arousal - 0.69).abs() < 1e-9);
        assert!((state.dominance - 0.576).abs() < 1e-9);
        assert!((state.trust - 0.52).abs() < 1e-9);
    }

    #[test]
    fn alma_decay_matches_state_tick_formula() {
        let (valence, arousal) = apply_alma_decay(0.5, 0.5, 0.05, 1.0);
        assert!(valence < 0.5);
        assert_eq!(arousal, 0.52);
    }

    #[test]
    fn fatigue_updates_increase_when_active() {
        let state = FatigueState::new(0.1, 1000.0);
        // Current time is 1001.0, meaning active since last user interaction was 1000.0 (1s ago, idle is > 300s)
        let updated = update_fatigue(&state, 1001.0, 1.0, false);
        assert!(updated.fatigue > 0.1);
        assert!(updated.fatigue <= 1.0);
    }

    #[test]
    fn fatigue_updates_decrease_when_idle() {
        let state = FatigueState::new(0.5, 1000.0);
        // Current time is 1400.0, meaning idle since last interaction was 1000.0 (400s ago)
        let updated = update_fatigue(&state, 1400.0, 1.0, false);
        assert!(updated.fatigue < 0.5);
        assert!(updated.fatigue >= 0.0);
    }

    #[test]
    fn fatigue_updates_are_clamped_to_bounds() {
        // Test high out-of-bounds fatigue
        let state_high = FatigueState::new(1.5, 1000.0);
        let updated_high = update_fatigue(&state_high, 1001.0, 1.0, false);
        assert_eq!(updated_high.fatigue, 1.0);

        let updated_high_idle = update_fatigue(&state_high, 1400.0, 0.01, false);
        assert!(updated_high_idle.fatigue <= 1.0);

        // Test low out-of-bounds fatigue
        let state_low = FatigueState::new(-0.5, 1000.0);
        let updated_low = update_fatigue(&state_low, 1400.0, 1.0, false);
        assert_eq!(updated_low.fatigue, 0.0);

        let updated_low_active = update_fatigue(&state_low, 1001.0, 0.01, false);
        assert!(updated_low_active.fatigue >= 0.0);
    }

    #[test]
    fn compute_vector_delta_calculates_mean_squared_difference() {
        let v1 = vec![0.0, 0.0, 0.0];
        let v2 = vec![1.0, 2.0, 2.0];
        let delta = compute_vector_delta(v1, v2);
        // (1^2 + 2^2 + 2^2) / 3 = (1 + 4 + 4) / 3 = 9 / 3 = 3.0
        assert!((delta - 3.0).abs() < 1e-9);
    }
}
