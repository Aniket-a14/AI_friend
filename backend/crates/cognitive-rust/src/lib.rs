use pyo3::prelude::*;
use pyo3::types::{PyModule, PyDict};

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
    fn to_dict(&self, py: Python<'_>) -> PyResult<Py<PyDict>> {
        let dict = PyDict::new(py);
        dict.set_item("relevance", self.relevance)?;
        dict.set_item("novelty", self.novelty)?;
        dict.set_item("goal_congruence", self.goal_congruence)?;
        dict.set_item("agency", self.agency)?;
        dict.set_item("norm_alignment", self.norm_alignment)?;
        dict.set_item("relationship_impact", self.relationship_impact)?;
        Ok(dict.unbind())
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
#[pyo3(signature = (event_content, event_type, emotional_bias, trust, recent_contents, identity_boundaries, pitch_f0=None, energy_rms=None))]
pub fn compute_appraisal(
    event_content: &str,
    event_type: &str,
    emotional_bias: f64,
    trust: f64,
    recent_contents: Vec<String>,
    identity_boundaries: Vec<String>,
    pitch_f0: Option<f64>,
    energy_rms: Option<f64>,
) -> AppraisalVector {
    let relevance = match event_type {
        "USER_MESSAGE" => 1.0,
        "SYSTEM_TICK" => 0.1,
        _ => 0.5,
    };
    let novelty = compute_novelty(event_content, &recent_contents);
    let mut goal_congruence = emotional_bias.clamp(-1.0, 1.0);
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

    // High energy yells (energy > 0.15) or extremely high pitch (F0 > 250Hz) shifts appraisal
    let pitch = pitch_f0.unwrap_or(150.0);
    let energy = energy_rms.unwrap_or(0.0);
    if energy > 0.15 || pitch > 250.0 {
        goal_congruence = (goal_congruence - 0.3).clamp(-1.0, 1.0);
        relationship_impact = (relationship_impact - 0.2).clamp(-1.0, 1.0);
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
    sum / v1.len() as f64
}

#[pyfunction]
pub fn evaluate_acoustic_reflex(rms: f64, _zcr: f64, threshold: f64) -> bool {
    rms > threshold
}

/// HippoRAG-inspired Personalized PageRank power method for graph spreading
/// activation. This is a faithful port of the former in-Python hot loop and
/// preserves its exact semantics, including two deliberate behaviors:
///
///   * `degrees[i]` carries the ORIGINAL neighbor count of node `i`. When an
///     edge points at an entity outside the candidate set its resolved index is
///     omitted from `adjacency[i]`, yet the mass is still divided by the full
///     degree -- so that share leaks out of the graph, exactly as before.
///   * A node with degree 0 is dangling and redistributes its mass uniformly
///     across the seed set rather than the whole graph.
///
/// `adjacency[i]` holds the resolved (in-range) neighbor indices of node `i`;
/// `seeds` are the personalization/teleport nodes. Returns the rank vector of
/// length `adjacency.len()`.
#[pyfunction]
#[pyo3(signature = (adjacency, degrees, seeds, damping, iterations))]
pub fn personalized_pagerank(
    adjacency: Vec<Vec<usize>>,
    degrees: Vec<usize>,
    seeds: Vec<usize>,
    damping: f64,
    iterations: usize,
) -> Vec<f64> {
    let n = adjacency.len();
    if n == 0 || seeds.is_empty() {
        return vec![0.0; n];
    }

    let seed_share = 1.0 / seeds.len() as f64;
    let mut p0 = vec![0.0_f64; n];
    for &s in &seeds {
        if s < n {
            p0[s] = seed_share;
        }
    }

    let mut p = p0.clone();
    for _ in 0..iterations {
        let mut p_next = vec![0.0_f64; n];
        for i in 0..n {
            let degree = degrees.get(i).copied().unwrap_or(0);
            if degree > 0 {
                let share = p[i] / degree as f64;
                for &nb in &adjacency[i] {
                    if nb < n {
                        p_next[nb] += share;
                    }
                }
            } else {
                // Dangling node: redistribute uniformly across the seeds.
                let share = p[i] / seeds.len() as f64;
                for &s in &seeds {
                    if s < n {
                        p_next[s] += share;
                    }
                }
            }
        }
        for i in 0..n {
            p_next[i] = damping * p_next[i] + (1.0 - damping) * p0[i];
        }
        p = p_next;
    }
    p
}

#[pyfunction]
pub fn score_memories_actr_sqlite(
    query_vector: Vec<f64>,
    rows: Vec<Bound<'_, PyDict>>,
    excluded: std::collections::HashSet<String>,
    current_valence: f64,
    current_arousal: f64,
    current_cortisol: f64,
    decay_rate: f64,
    spread_weight: f64,
    threshold: f64,
    now_ts: f64,
) -> PyResult<Vec<(usize, f64, f64)>> {
    let mut results = Vec::new();
    for (index, row) in rows.iter().enumerate() {
        let content: String = match row.get_item("content")? {
            Some(val) => val.extract::<String>().unwrap_or_default(),
            None => String::new(),
        };
        if excluded.contains(&content) {
            continue;
        }

        // Get embedding
        let emb_val: Vec<f64> = match row.get_item("embedding")? {
            Some(val) => {
                if val.is_none() {
                    Vec::new()
                } else if let Ok(s) = val.extract::<String>() {
                    let s_trimmed = s.trim_matches(|c| c == '[' || c == ']');
                    let mut parsed_ok = true;
                    let parsed: Vec<f64> = s_trimmed
                        .split(',')
                        .map(|x| {
                            let trimmed = x.trim();
                            if trimmed.is_empty() {
                                return 0.0;
                            }
                            match trimmed.parse::<f64>() {
                                Ok(v) => v,
                                Err(_) => {
                                    eprintln!("[Rust SQLite Fallback] Warning: Failed to parse float token {:?} in embedding database field.", trimmed);
                                    parsed_ok = false;
                                    0.0
                                }
                            }
                        })
                        .collect();
                    if parsed_ok {
                        parsed
                    } else {
                        Vec::new()
                    }
                } else if let Ok(v) = val.extract::<Vec<f64>>() {
                    v
                } else {
                    Vec::new()
                }
            }
            None => Vec::new(),
        };

        if emb_val.len() != query_vector.len() || query_vector.is_empty() {
            continue;
        }

        // Cosine similarity
        let dot: f64 = query_vector.iter().zip(emb_val.iter()).map(|(x, y)| x * y).sum();
        let mag1 = query_vector.iter().map(|x| x * x).sum::<f64>().sqrt();
        let mag2 = emb_val.iter().map(|x| x * x).sum::<f64>().sqrt();
        let similarity = if mag1 * mag2 > 0.0 { dot / (mag1 * mag2) } else { 0.0 };

        let recall_count = match row.get_item("recall_count")? {
            Some(val) => {
                if val.is_none() {
                    1.0
                } else {
                    val.extract::<i64>().unwrap_or(1).max(1) as f64
                }
            }
            None => 1.0,
        };

        let last_recall_ts = match row.get_item("_last_recall_ts")? {
            Some(val) => {
                if val.is_none() {
                    now_ts
                } else {
                    val.extract::<f64>().unwrap_or(now_ts)
                }
            }
            None => now_ts,
        };

        let valence = match row.get_item("valence")? {
            Some(val) => {
                if val.is_none() {
                    0.0
                } else {
                    val.extract::<f64>().unwrap_or(0.0)
                }
            }
            None => 0.0,
        };

        let emotional_weight = match row.get_item("emotional_weight")? {
            Some(val) => {
                if val.is_none() {
                    0.0
                } else {
                    val.extract::<f64>().unwrap_or(0.0)
                }
            }
            None => 0.0,
        };

        let importance_score = match row.get_item("importance_score")? {
            Some(val) => {
                if val.is_none() {
                    0.5
                } else {
                    val.extract::<f64>().unwrap_or(0.5)
                }
            }
            None => 0.5,
        };

        let hours_since = ((now_ts - last_recall_ts) / 3600.0).max(0.001);

        // 2D/3D Emotional Distance
        let dist_emo = ((valence - current_valence).powi(2)
            + (emotional_weight - current_arousal).powi(2))
            .sqrt();

        // ACT-R base activation: ln(recall_count) - decay_rate * ln(hours_since + 1.0) + 1.5 * importance_score + 0.15 * (1.0 - dist_emo)
        let base_activation = recall_count.ln()
            - decay_rate * (hours_since + 1.0).ln()
            + 1.5 * importance_score
            + 0.15 * (1.0 - dist_emo);

        // Neuromodulatory distance mapping
        let effective_similarity = similarity
            * (1.0 + 0.1 * valence * emotional_weight - 0.2 * current_arousal * current_cortisol);

        let spread_activation = spread_weight * effective_similarity;
        let score = base_activation + spread_activation - 0.5 * dist_emo;

        if score > (threshold - 2.5) || importance_score >= 0.7 {
            results.push((index, score, similarity));
        }
    }
    Ok(results)
}

#[pyfunction]
pub fn generate_apra_trajectory(
    valence: f64,
    arousal: f64,
    dominance: f64,
    fatigue: f64,
) -> Vec<(u32, f64, f64, f64)> {
    let mut trajectory = Vec::with_capacity(60);
    for step in 0..60 {
        let t_ms = step * 50;

        // Dynamic Breathing & Pacing modulation (dip at start and end for natural breathing)
        let breathing_dampening = if t_ms < 200 {
            -0.15 * (1.0 - (t_ms as f64 / 200.0))
        } else if t_ms > 2700 {
            -0.15 * ((t_ms as f64 - 2700.0) / 300.0)
        } else {
            0.0
        };

        let step_rate = (1.0
            + 0.20 * arousal
            - 0.10 * valence
            - 0.25 * fatigue
            + breathing_dampening)
            .clamp(0.60, 1.80);

        // Sinusoidal micro-vibratory ripple to pitch (6Hz organic human vocal vibrato)
        let vibrato_ripple = 0.02 * (2.0 * std::f64::consts::PI * 6.0 * (t_ms as f64 / 1000.0)).sin();
        let step_pitch = (1.0
            + 0.05 * valence
            + 0.15 * arousal
            - 0.10 * dominance
            - 0.10 * fatigue
            + vibrato_ripple)
            .clamp(0.50, 2.00);

        // Volumetric envelope (smooth fade-in and fade-out near endpoints)
        let vol_envelope = if t_ms < 150 {
            t_ms as f64 / 150.0
        } else if t_ms > 2850 {
            (3000.0 - t_ms as f64) / 150.0
        } else {
            1.0
        };

        let step_volume = ((0.40 + 0.60 * dominance) * vol_envelope).clamp(0.10, 1.00);

        trajectory.push((
            t_ms,
            (step_rate * 100.0).round() / 100.0,
            (step_pitch * 100.0).round() / 100.0,
            (step_volume * 100.0).round() / 100.0,
        ));
    }
    trajectory
}

#[pymodule]
fn cognitive_rust(module: &Bound<'_, PyModule>) -> PyResult<()> {
    module.add_class::<AppraisalVector>()?;
    module.add_class::<PadState>()?;
    module.add_class::<PsychWeights>()?;
    module.add_class::<FatigueState>()?;
    module.add_function(wrap_pyfunction!(compute_appraisal, module)?)?;
    module.add_function(wrap_pyfunction!(score_memories_actr_sqlite, module)?)?;
    module.add_function(wrap_pyfunction!(generate_apra_trajectory, module)?)?;
    module.add_function(wrap_pyfunction!(update_pad_from_appraisal, module)?)?;
    module.add_function(wrap_pyfunction!(apply_alma_decay, module)?)?;
    module.add_function(wrap_pyfunction!(update_fatigue, module)?)?;
    module.add_function(wrap_pyfunction!(compute_vector_delta, module)?)?;
    module.add_function(wrap_pyfunction!(evaluate_acoustic_reflex, module)?)?;
    module.add_function(wrap_pyfunction!(personalized_pagerank, module)?)?;
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn appraisal_matches_python_heuristic_defaults() {
        let appraisal = compute_appraisal("hello friend", "USER_MESSAGE", 0.4, 0.5, vec![], vec![], None, None);

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

    #[test]
    fn ppr_single_iteration_two_node_ring() {
        // seed=node0, both connected. One power iteration, d=0.85.
        // node0 (deg1) pushes 1.0 -> node1; node1 (deg1) pushes 0.0 -> node0.
        // teleport: p0[0]=1.0 so node0 = 0.85*0 + 0.15*1 = 0.15; node1 = 0.85*1 = 0.85.
        let p = personalized_pagerank(vec![vec![1], vec![0]], vec![1, 1], vec![0], 0.85, 1);
        assert!((p[0] - 0.15).abs() < 1e-12);
        assert!((p[1] - 0.85).abs() < 1e-12);
    }

    #[test]
    fn ppr_dangling_node_redistributes_to_seeds() {
        // node0 has degree 0 (dangling), node1 -> node0. seed=node0.
        // node0 dangling pushes its full mass back to the seed set {0}.
        let p = personalized_pagerank(vec![vec![], vec![0]], vec![0, 1], vec![0], 0.85, 1);
        assert!((p[0] - 1.0).abs() < 1e-12);
        assert!((p[1] - 0.0).abs() < 1e-12);
    }

    #[test]
    fn ppr_degree_greater_than_resolved_neighbors_leaks_mass() {
        // node0 reports degree 2 but only one neighbor resolved in-set: half its
        // mass leaks out of the graph, exactly as the legacy Python loop did.
        // share = 1.0/2 = 0.5 -> node1; node0 = 0.15 (teleport), node1 = 0.85*0.5.
        let p = personalized_pagerank(vec![vec![1], vec![]], vec![2, 0], vec![0], 0.85, 1);
        assert!((p[0] - 0.15).abs() < 1e-12);
        assert!((p[1] - 0.425).abs() < 1e-12);
        assert!(p[0] + p[1] < 1.0); // mass genuinely leaked
    }

    #[test]
    fn ppr_empty_seeds_returns_zero_vector() {
        let p = personalized_pagerank(vec![vec![1], vec![0]], vec![1, 1], vec![], 0.85, 3);
        assert_eq!(p, vec![0.0, 0.0]);
    }
}
