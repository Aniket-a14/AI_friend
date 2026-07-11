\documentclass[conference]{IEEEtran}
\IEEEoverridecommandlockouts
\usepackage{cite}
\usepackage{amsmath,amssymb,amsfonts}
\usepackage{algorithmic}
\usepackage{graphicx}
\usepackage{textcomp}
\usepackage{xcolor}
\usepackage{booktabs}
\usepackage{array}
\usepackage{hyperref}
\usepackage{microtype}

\def\BibTeX{{\rm B\kern-.05em{\sc i\kern-.025em b}\kern-.08em
    T\kern-.1667em\lower.7ex\hbox{E}\kern-.125emX}}

\begin{document}

\title{A Novel Framework for Improved Cognitive, Emotional, and Vocal Interaction in Conversational Humanoid Robots Assisted by Hybrid Neuromodulatory Network Architecture}

\author{
\IEEEauthorblockN{Aniket Saha}
\IEEEauthorblockA{\textit{Department of Computer Science and Engineering} \\
\textit{Lovely Professional University}\\
Phagwara, Punjab \\
aniketsahaworkspace@gmail.com}
\and
\IEEEauthorblockN{Salil Batra}
\IEEEauthorblockA{\textit{Department of Computer Science and Engineering} \\
\textit{Lovely Professional University}\\
Phagwara, Punjab \\
salilbatra40@gmail.com}
}

\maketitle

\begin{abstract}
Humanoid robots struggle to maintain conversational realism and co-presence. Centralized request-response setups introduce lag, drift, and robotic emotions. To break this bottleneck, this work presents a novel framework using the Hybrid Neuromodulatory Network Architecture (HNNA) that shifts computation to a decentralized edge event bus, splitting execution into sub-15ms reflexive routines (System Part A) and deliberative reasoning (System Part B). At the core, a neuromodulatory engine models pleasure-arousal-dominance (PAD) states alongside cortisol, dopamine, and fatigue levels. These simulated endocrine signals gate memory recall and adapt vocal prosody in real time. Local compute takes only 1.92 ms under hardware acceleration, with a total edge pipeline latency of 5.44 ms. Dialog remains coherent across 50 turns (92.2\% average coherence), and Theory of Mind tracking yields a valence error of 0.032, further, speculative turn-taking resolves barge-in conflicts in 104.3 ms -- a 4.6x speedup. Running entirely on edge resources, the cognitive mesh requires a tiny 0.99 W power envelope and caps memory search at 1.07 ms.
\end{abstract}

\begin{IEEEkeywords}
Conversational Humanoid Robots, Cognitive Architectures, Emotional Interaction, Vocal Interaction, Hybrid Neuromodulatory Networks.
\end{IEEEkeywords}

\section{Introduction}

Standard humanoid dialogue stacks voice recognition, reasoning, and speech synthesis sequentially. This structure piles up latency, turning natural dialogue into a series of awkward pauses. For companion robots, real-time response generation is only half the battle, where they must also sustain a stable persona and track emotional context over hours of conversation.

\vspace{0.2cm}

Current systems fall short on multiple fronts.In natural human conversation, the average response transitions is roughly 200 ms \cite{skantze2021}, yet cloud-dependent routing struggles to meet this threshold. In long sessions, context buildup dilutes prompt instructions, causing identity drift. Simple categorical emotion tags also fail to model the continuous shifts of human affect. Finally, standard voice activity detectors cannot handle overlap or interruptions without causing conversational lag. Solving these issues requires merging low-latency reflex loops with continuous emotional models and memory-efficient backends.

\subsection{Objectives}

The Hybrid Neuromodulatory Network Architecture (HNNA) tackles these bottlenecks. Designed as a distributed edge mesh, this framework segregates sub-15ms reflex actions (System Part A, written in Rust via PyO3) from heavy cognitive appraisals and memory queries (System Part B, written in Python). Taking cues from biological systems, HNNA models the endocrine dynamics simulating cortisol, dopamine, fatigue, and continuous PAD states to steer memory projection and vocal prosody. This division of labor maintains quick response times while organically adapting the robot's behavior.

\subsection{Contributions}

The primary contributions are:

\begin{itemize}
\setlength{\itemsep}{6pt}
\setlength{\parskip}{0pt}
\setlength{\parsep}{0pt}

\item \textit{Decoupled Part A/B execution}: A dual-layer architecture separating sub-15ms reflexive interrupts from deliberative cognitive loops to minimize event-routing latency.

\item \textit{Endocrine-modulated behavior}: An integrated model of continuous PAD dynamics and simulated endocrine levels regulating prompt engineering and voice prosody.

\item \textit{ACT-R bounded graph retrieval}: A hybrid memory structure combining Personalized PageRank and ACT-R recency decay to prune context search spaces.

\item \textit{Single-pass co-generation}: A parallel parsing pipeline producing text tokens and emotional metadata simultaneously for low-latency TTS streaming.

\end{itemize}

\vspace{0.2cm}

Section II reviews relevant literature on turn-taking, memory modeling, and edge platforms. Section III presents the methodology of the HNNA framework. Section IV details experimental results, followed by concluding remarks in Section V.


\section{Related Work}

Building humanoid conversational engines requires merging turn-taking reflexes, emotional models, cognitive memory, and edge messaging. Each field has grown independently, but uniting them to enable real-time robotic co-presence remains a major challenge.

\subsection{Vocal Interaction and Turn-Taking Latency}

Human dialogue flows within an avergae of 200 ms turn-exchange window \cite{skantze2021}. Early voice activity detection (VAD) relied on raw acoustic energy thresholds \cite{raux2009}, leading to high false-alarm rates or latency. Modern Voice Activity Projection (VAP) tracks turn boundaries via joint acoustic and lexical analysis \cite{inoue2024, skantze2025}. Multimodal models improve these predictions by tracking head movement, gaze, and gestures \cite{lala2019}. Yet sequential processing pipelines (ASR-LLM-TTS) still create bottlenecks, slowing interactions on edge systems.

\subsection{Emotional Appraisal and Affective Computing}

Coherence in dialogue demands emotional realism. The three-dimensional Pleasure-Arousal-Dominance (PAD) model represents affect as a continuous coordinate space, avoiding the rigidity of discrete emotion labels \cite{mehrabian1996}. Appraisal systems such as the EMA and the ALMA model affective trajectories based on situational stimuli and internal states \cite{marsella2009, gebhard2005}. Other theories, such as OCC, link these appraisals to behavioral updates \cite{ortony1988}. However, most systems reduce these multi-dimensional states to static text prompts, failing to modulate dialogue flow dynamically \cite{picard1997, scherer2005}.

\subsection{Cognitive Memory and Neuromodulatory Gating}

Dialogue consistency over time depends on memory indexing. Cognitive architectures such as ACT-R evaluate memory activation based on recency and usage frequency \cite{anderson2004, laird2012}. Concurrently, graph-based methods model semantic networks and run algorithms such as Personalized PageRank for multi-hop retrieval \cite{gutierrez2024}, thereby mimicking neocortical consolidation \cite{teyler1986, mcclelland1995}. While graph structures provide rich context, deep traversals slow down edge processing. This demands memory-gating methods that prioritize recall through active emotional and cognitive states.

\subsection{Edge Middleware and Interprocess Communication}

Real-time perception and reasoning require lightweight, fast messaging. ROS2 is the standard middleware for robotics, but its heavy DDS-based transport layer adds CPU overhead \cite{maruyama2016}. Lightweight publish-subscribe brokers like NATS JetStream offer faster routing for event-driven micro-agents \cite{nats2019}. Additionally, executing reflex routines in Rust and calling them from Python via PyO3 minimizes computational latency \cite{zhang2022}.

\vspace{0.2cm}

Decoupled reflexes, continuous emotion vectors, bounded graph memory, and fast edge messaging are essential for real-time systems. The proposed HNNA framework integrates these pillars into a single, cohesive neuromodulatory architecture.

\section{Proposed Framework and Methodology}

HNNA maps cognitive, affective, and verbal interactions onto a decentralized micro-agent mesh connected by a local event bus (Fig.~\ref{fig:system_architecture}).

\begin{figure*}[!t]
\centering
\includegraphics[width=2\columnwidth]{scripts/results/system_architecture.png}
\caption{System architecture and processing workflow of the HNNA framework.}
\label{fig:system_architecture}
\end{figure*}

\subsection{System Topology and Behavioral Decision Routing}

Micro-agents exchange contracts serialized via \texttt{orjson} over NATS. To capture social alignment, a Theory of Mind (ToM) module estimates user valence and arousal by analyzing gaze trajectories \cite{krafka2016} and facial landmarks \cite{kollias2021}. Concurrently, a User Knowledge Model extracts dialogue keywords to update a working set. Subjective user beliefs are stored in Neo4j as \texttt{BELIEVES} edges, allowing the system to match discrepancies against ground-truth facts and resolve misconceptions.

A Behavior Tree evaluates active goals $g \in \{\text{ENGAGE}, \text{COMFORT}, \text{INFORM}, \text{TEASE}, \text{PROTECT}\}$ to route conversational intents \cite{laird2012, gebhard2005}. A Temporal-Difference (TD) reinforcement learning rule dynamically updates goal utilities:

\vspace{0.1cm}

$U_g(t) = U_g(t-1) + \alpha_{rl} [R(t) - U_g(t-1)]$, with learning rate $\alpha_{rl} = 0.1$. The step reward $R(t)$ combines user valence and gaze duration. The tree feeds these updated utilities into the multi-attribute scoring model in \eqref{eq:maut_utility} to prioritize historically successful behaviors, maximizing:
\begin{equation}
\begin{split}
U(g) = & w_g G(g) + w_e E(g) \\
& + w_i I(g) + w_c C(g),
\end{split}
\label{eq:maut_utility}
\end{equation}
where $w_g, w_e, w_i, w_c$ represent weight parameters. To smooth intent selection and avoid goal thrashing, an exponential filter dampens goal transitions:
\begin{equation}
\begin{split}
S_g(t) = & (1 - \rho) S_g(t-1) \\
& + \rho U_g(t),
\end{split}
\label{eq:temporal_smoothing}
\end{equation}
utilizing a persistence coefficient $\rho = 0.35$.


\subsection{Neuromodulatory Affect and Vocal Prosody Dynamics}

The emotional system maps affect to a continuous PAD vector $\vec{S}(t)$ that decays over time back to a baseline state $\vec{S}_0$:
\begin{equation}
\begin{split}
\vec{S}(t) = & \vec{S}_0 + (\vec{S}(t_0) - \vec{S}_0) \\
& \cdot e^{-\lambda (t - t_0)},
\end{split}
\label{eq:alma_decay}
\end{equation}
with decay rate $\lambda \in [0.1, 0.5]$ \cite{gebhard2005}. Empathetic or comforting inputs trigger immediate spikes in dopamine ($D_t$) and valence ($V_t$) levels \cite{picard1997, scherer2005}:
\begin{equation}
D_t = \min(1.0, D_{t^-} + 0.25 e^{-\eta N_c}),
\label{eq:dopamine_spike}
\end{equation}
\begin{equation}
V_t = \min(1.0, V_{t^-} + 0.15 e^{-\eta N_c}),
\label{eq:valence_spike}
\end{equation}
where $N_c$ counts consecutive stimuli and $\eta = 0.4$ represents the decay rate. The active PAD state and endocrine variables (cortisol $C$, dopamine $D_p$, and fatigue $F$) combine into a structured text prefix:
\begin{equation}
\mathcal{P} = \text{[PAD: } P, A, D\text{] [Endo: } C, D_p, F\text{]},
\label{eq:prefix_header}
\end{equation}
The generation engine prepends this prefix to steer the LLM's dialogue style.

This architecture translates cognitive states directly into multimodal behaviors. Affective shifts trigger endocrine updates, which dynamically alter memory recall scoring (detailed in Section \ref{sec:memory_consolidation}) and adjust prosody knobs specifically speaking rate $S_f$, pitch shift $P_f$, and pause bias $B_p$ to generate paralinguistic variation \cite{mehrabian1996, scherer2005}:
\begin{equation}
\begin{split}
S_f = & \operatorname{clamp}\Big(1.0 + \tanh\big(0.20 A \\
& - 0.10 P - 0.25 F\big), 0.6, 1.8\Big),
\end{split}
\label{eq:speaking_rate}
\end{equation}
\begin{equation}
\begin{split}
P_f = & \operatorname{clamp}\Big(1.0 + \tanh\big(0.05 P \\
& + 0.15 A - 0.10 D - 0.10 F\big), 0.5, 2.0\Big),
\end{split}
\label{eq:pitch_shift}
\end{equation}
\begin{equation}
B_p = 1.0 - A.
\label{eq:pause_bias}
\end{equation}
A linear crossfader smooths audio output over a 15 ms window to prevent click noise:
\begin{equation}
\begin{split}
y[i] = & \left(1 - \frac{i}{N}\right) x_{prev}[i] \\
& + \left(\frac{i}{N}\right) x_{curr}[i],
\end{split}
\label{eq:crossfade}
\end{equation}
operating across index $i$ over $N$ samples.

\subsection{Memory Architecture and Consolidation}
\label{sec:memory_consolidation}

The system organizes memory across four tiers: active cache (Redis), logs (SQLite), semantic vectors (Qdrant), and relational facts (Neo4j).

\vspace{0.2cm}

To balance latency and search precision, the retrieval system runs dynamic-resolution Matryoshka Representation Learning (MRL) gating \cite{kusupati2022}. In relaxed states, search utilizes full 768-dimensional BGE-M3 embeddings. High stress (arousal or cortisol > 0.8) triggers dynamic truncation: the system cuts query and candidate vectors down to 256 or 512 dimensions and zero-pads the remainder to match database schemas, saving CPU cycles. Over the Neo4j semantic network, Personalized PageRank (PPR) indexes active seed nodes:
\begin{equation}
\vec{pr} = \alpha \mathbf{M} \vec{pr} + (1 - \alpha) \vec{p},
\label{eq:pagerank}
\end{equation}
\begin{equation}
p_u = \begin{cases}
\frac{1}{|V_{seed}|}, & \text{if } u \in V_{seed} \\
0, & \text{otherwise}
\end{cases}
\label{eq:pagerank_init}
\end{equation}
simulating hippocampal indexing pathways \cite{gutierrez2024}. Pruning nodes with scores below $10^{-4}$ caps graph search times at 10 ms.


Memory recall scoring integrates ACT-R base-level activation:
\begin{equation}
\begin{split}
A_i = & \ln\left( \sum_{j=1}^{n} (t - t_j)^{-d} \right) \\
& + \sum_{k} W_k S_{ki},
\end{split}
\label{eq:actr_activation}
\end{equation}
with a decay rate $d = 0.5$ \cite{anderson2004}. The composite recall score $\text{Score}_i$ for memory block $i$ is:
\begin{equation}
\begin{split}
\text{Score}_i = & A_i + w_g \vec{pr}[i] \\
& + w_s \text{Sim}_{gated}(v_i, q) \\
& - w_d d_{emo}(v_i, \vec{S}),
\end{split}
\label{eq:recall_score}
\end{equation}
where $w_g, w_s, w_d$ are relative weights. The emotional distance metric is:
\begin{equation}
d_{emo}(v_i, \vec{S}) = \|\vec{e}_i - \vec{S}_{V,A}\|_2,
\label{eq:emotional_distance}
\end{equation}
measuring distance between the memory's tag $\vec{e}_i$ and the active mood state $\vec{S}_{V,A}$:
\begin{equation}
\vec{e}_i = [P_{mem}, A_{mem}]^T,
\label{eq:mem_vector}
\end{equation}
\begin{equation}
\vec{S}_{V,A} = [P(t), A(t)]^T.
\label{eq:active_vector}
\end{equation}
Gated similarity simulates stress-induced memory blocking:
\begin{equation}
\begin{split}
\text{Sim}_{gated}(v_i, q) = & \text{Sim}(v_i, q) \\
& \cdot \big(1 + \gamma P_{mem} w_e \\
& - \delta \cdot A(t) \cdot C(t)\big),
\end{split}
\label{eq:gated_sim}
\end{equation}
where $\gamma$ and $\delta$ are gating coefficients, $P_{mem}$ represents the memory's pleasure value, $w_e$ is the emotional salience weight \cite{easterbrook1959}, $A(t)$ is active arousal, and $C(t)$ is the cortisol level at time $t$. The formula combines dense and sparse similarities, applying a penalty under high stress. The system prunes nodes scoring $\text{Score}_i < -2.0$.

\vspace{0.2cm}

During sleep cycles, consolidation routines move SQLite dialogue turns and Qdrant facts into permanent storage. To prioritize important events, consolidation is gated by an Episodic Saliency Index: $\text{ESI} = 0.6 \cdot \text{Arousal} + 0.4 \cdot \text{Cortisol}$. The system discards low-saliency events ($\text{ESI} < 0.4$) and trains QLoRA adapters on the remaining episodes to update the LLM weights $\theta$:
\begin{equation}
\begin{split}
\mathcal{L}_{\text{sleep}}(\theta) = & \mathcal{L}_{\text{new}}(\theta) \\
& + \lambda \mathcal{L}_{\text{anchor}}(\theta),
\end{split}
\label{eq:consolidation_loss}
\end{equation}
where $\theta$ represents the adapter parameters, $\mathcal{L}_{\text{new}}$ is the cross-entropy loss on new dialogue turns, and anchor regularization $\mathcal{L}_{\text{anchor}}$ prevents biographical decay scaled by parameter $\lambda \ge 0.5$.

\subsection{Dialogue Generation and Turn-Taking Protocol}

To keep conversation fluid, a fine-tuned LLM co-generates verbal replies and emotional meta-tags in a single forward pass. This streams audio tokens to the TTS engine within 10 ms, while XML tags asynchronously update the PAD state. Response latency is further reduced via Voice Activity Projection (VAP). The coordinator monitors acoustic and lexical parameters, initiating speculative pre-generation when turn transition probability $P_{trans} \ge 0.7$ before the user finishes speaking, committing the response immediately upon user silence.

\vspace{0.2cm}

Interruption management runs in two phases:
\begin{enumerate}
    \setlength{\itemsep}{1pt}
    \setlength{\parskip}{0pt}
    \setlength{\parsep}{0pt}
    \item[1)] Speculative Ducking: If speech probability exceeds 0.75, audio output drops by 70\% within 15 ms using a linear crossfade.
    \item[2)] Semantic Verification: A local Whisper engine verifies if a semantic turn occurred; if not, audio volume is restored.
\end{enumerate}

During pauses, a thought scheduler evaluates proactive cue timing \cite{lala2019}:
\begin{equation}
\begin{split}
T_{\text{thought}} = & f_{\text{LLM}}\big(E_{\text{agent}}, \\
& \text{IdleTime}, \text{Context}\big),
\end{split}
\label{eq:proactive_thought}
\end{equation}
If silence exceeds a dynamic threshold, the engine evaluates \eqref{eq:proactive_thought} to steer proactive robot check-ins. The soft-ducking reflex remains active during robot speech, allowing instant 15 ms volume attenuation and semantic turn validation upon user barge-in.

Section IV validates these subsystems under execution constraints.

\section{Results and Discussions}

Empirical validation profiles HNNA across edge resources, turn latency, memory recall, and social coherence. Multi-turn dialogue stability was tracked using cosine similarity over 50 turns. In addition, Theory of Mind (ToM) accuracy was benchmarked via Mean Absolute Error (MAE) on 1,000 scenarios. Interruption handling was assessed using 1,000 multi-intent probes, and t-tests verified statistical significance ($p < 0.001$).

\subsection{Vocal Interaction and Turn-Taking Performance}

Speculative turn-taking resolves barge-in conflicts in 104.3 ms, outperforming cloud-based pipelines that exceed 200 ms. Over 1,000 intent probes, the System Part B classifier reaches 85.7\% accuracy (162.79 ms mean latency, Fig.~\ref{fig:confusion_matrix}) with 97.8\% recall on threats (F1: 0.840) and 96.1\% precision.

\begin{figure}[!h]
\centering
\includegraphics[width=1\columnwidth]{scripts/results/cognitive_confusion_matrix.png}
\caption{Intent routing classification performance across CHAT, THREAT, TASK, and AFFECTIVE modes.}
\label{fig:confusion_matrix}
\end{figure}

The conflict resolver achieves a 93.0\% barge-in accuracy (F1: 94.8\%) with a 15 ms soft-ducking reflex and 104.3 ms semantic verification (a 4.6-fold speedup, Fig.~\ref{fig:realism_comparisons}). Capping memory queries at 1.07 ms prevents blocking delays during semantic turn-taking. This allows the dialogue manager to cross-reference conversational states and complete verification within the 104.3 ms window. Concurrently, the ToM model yields MAEs of 0.032 (valence) and 0.041 (arousal) for localized, continuous classification from facial and vocal landmarks, outperforming zero-shot foundation models like GPT-4o (0.28) and Claude 3.5 (0.32) evaluated on equivalent text-only prompt descriptions of the trajectories (Fig.~\ref{fig:tom_errors}). This performance difference highlights the efficiency of specialized edge models operating directly on raw sensory features compared to large, general-purpose text foundation models.

\begin{figure}[!h]
\centering
\includegraphics[width=1\columnwidth]{scripts/results/human_realism_comparisons.png}
\caption{Speech turn-taking barge-in latency (A), Theory of Mind MAE error (B), and memory retrieval speedup ratio (C) comparing bounded vs. unbounded search space.}
\label{fig:realism_comparisons}
\end{figure}

\begin{figure}[!h]
\centering
\includegraphics[width=1\columnwidth]{scripts/results/cognitive_tom_errors.png}
\caption{Theory of Mind valence and arousal mean absolute error (MAE) comparisons against baseline models.}
\label{fig:tom_errors}
\end{figure}

\subsection{Cognitive Memory and Graph Retrieval Performance}

Scaling database sizes to 100,000 distractors (representing a 19-year developmental history simulated over a 1-year database timeline) shows that ACT-R pruning preserves a Recall@5 of 87.5\% while capping vector retrieval latency at 1.07 ms (vs. 84.6 ms without pruning, Fig.~\ref{fig:recall_efficiency}). This sub-millisecond retrieval pathway prevents LLM attention dispersion, thereby eliminating identity drift and token-generation delays. Furthermore, graph indexing and PPR caching reduce 3-hop Neo4j traversals to 0.197 ms (8.85 ms uncached, Table~\ref{tab:graph_traversal}), allowing the Behavior Tree to query relational knowledge in real time.

\begin{figure}[!h]
\centering
\includegraphics[width=1\columnwidth]{scripts/results/cognitive_rag_recall.png}
\caption{Recall@K curve (left) and Retrieval Latency scaling over database size (right) comparing activation-pruned Search Space (Pruned) vs. Unbounded Semantic Search Space (No Pruning).}
\label{fig:recall_efficiency}
\end{figure}

\begin{table}[!h]
\caption{Multi-Hop Graph Memory Traversal Latency}
\begin{center}
\footnotesize
\begin{tabular}{|l|c|c|c|}
\hline
\textbf{Hops} & \textbf{Cached (ms)} & \textbf{Uncached (ms)} & \textbf{Std DB (ms)} \\
\hline
1 & 0.164 & 1.25 & 8.50 \\
\hline
2 & 0.181 & 3.42 & 24.20 \\
\hline
3 & 0.197 & 8.85 & 84.60 \\
\hline
\end{tabular}
\label{tab:graph_traversal}
\end{center}
\end{table}

\subsection{Pipeline Performance Buffer and Resource Efficiency}

Bounding pre- and post-LLM processing latency is critical to maximize LLM generation budgets. As shown in Table~\ref{tab:latency_pathway}, components run within budget, yielding a 5.44 ms total pipeline latency and 11.56 ms of buffer. This is achieved by running the System Part A reflex in parallel with the System Part B appraisal and memory retrieval.

Under local execution on hardware-accelerated target platforms, the software orchestrator agents (including the NATS broker, SQLite state telemetry, Redis caches, and brain/state cognitive services) consume a combined active power envelope of 0.99 W (excluding physical GPU/NPU cores during active LLM inference or audio TTS generation). The bounded vector memory retrieval pathway exhibits a mean latency of 1.07 ms across 100,000 distractors, using Matryoshka Representation Learning to compress search dimensions under elevated stress. Similarly, cached Neo4j graph queries yield a 3-hop traversal latency of 0.197 ms (8.85 ms uncached; 84.60 ms baseline for a standard DB), validating that localized cognitive meshes can operate efficiently within edge robotics power budgets.

\begin{table}[!h]
\caption{Pre-LLM and Post-LLM Pipeline Latencies}
\begin{center}
\footnotesize
\begin{tabular}{|p{2.6cm}|c|c|c|}
\hline
\textbf{Component} & \textbf{Opt. (ms)} & \textbf{Budget (ms)} & \textbf{Status} \\
\hline
Audio Ingest & 0.04 & 5.00 & Passed \\
\hline
DSP Feature & 0.04 & 1.00 & Passed \\
\hline
Soft-Attn & 0.02 & 1.00 & Passed \\
\hline
Text Segment & 0.16 & 10.00 & Passed \\
\hline
Threat Scan & 0.24 & 2.00 & Passed \\
\hline
Memory Search & 1.07 & 8.00 & Passed \\
\hline
State Appraisal & 0.06 & 5.00 & Passed \\
\hline
Temp. Mod. & 0.002 & 1.00 & Passed \\
\hline
End-to-End & 5.44 & 17.00 & Passed \\
\hline
\end{tabular}
\label{tab:latency_pathway}
\end{center}
\end{table}

\subsection{Comparative Analysis with State-of-the-Art Baselines}

\begin{table}[!h]
\caption{State-of-the-Art Memory and Realism Comparison}
\begin{center}
\footnotesize
\begin{tabular}{|l|c|c|c|c|}
\hline
\textbf{Model} & \textbf{ToM MAE} & \textbf{Rec@5} & \textbf{Lat. (ms)} & \textbf{Vocal \%} \\
\hline
GPT-4o & 0.280 & 65.6\% & $\sim$300 & -- \\
\hline
Claude 3.5 & 0.320 & 65.6\% & $\sim$350 & -- \\
\hline
Std RAG & 0.380 & 77.0\% & 84.60 & 74.3\% \\
\hline
HNNA & 0.032 & 87.5\% & 1.07 & 94.4\%--95.3\% \\
\hline
\end{tabular}
\label{tab:cognitive_realism}
\end{center}
\end{table}

As shown in Table~\ref{tab:cognitive_realism}, HNNA achieves a paralinguistic precision of 94.4\%--95.3\% and a Recall@5 of 87.5\% (at 1.07 ms), outperforming standard RAG \cite{kang2024}. Continuous neuro-modulatory mapping gates memory recall and structures prompt prefixes based on PAD-endocrine states. Furthermore, the ToM valence MAE of 0.032 outperforms zero-shot models on emergence benchmarks \cite{kosinski2024}.

\section{Conclusion}

The HNNA framework provides a decentralized, event-driven cognitive core that improves cognitive, emotional, and vocal interaction in conversational humanoid platforms. Decoupling reflexive turn-taking from deliberative emotional appraisal and memory routing maintains social realism within human turn boundaries. Splitting execution into System Part A and Part B processes allows the platform to run deep cognitive, emotional, and Theory of Mind updates at the edge within a restricted power envelope. Future work will focus on integrating body-language rendering, conducting longitudinal user studies, performing ablation studies on graph-memory retrieval pathways, and exploring end-to-end multi-modal speech networks.

\begin{thebibliography}{00}

\bibitem{skantze2021}
G. Skantze, ``Turn-taking in Conversational Systems and Human-Robot Interaction: A Review,'' \emph{Computer Speech \& Language}, vol. 67, p. 101178, May 2021.

\bibitem{raux2009}
A. Raux and M. Eskenazi, ``A Finite-State Turn-Taking Model for Spoken Dialog Systems,'' in \emph{Proceedings of Human Language Technologies: The 2009 Annual Conference of the North American Chapter of the Association for Computational Linguistics (NAACL-HLT 2009)}, Boulder, CO, USA, June 2009, pp. 629--637.

\bibitem{inoue2024}
K. Inoue, B. Jiang, E. Ekstedt, T. Kawahara, and G. Skantze, ``Multilingual Turn-taking Prediction Using Voice Activity Projection,'' in \emph{Proceedings of the 2024 Joint International Conference on Computational Linguistics, Language Resources and Evaluation (LREC-COLING)}, Torino, Italy, May 2024, pp. 11873--11883.

\bibitem{skantze2025}
G. Skantze and B. Irfan, ``Applying General Turn-taking Models to Conversational Human-Robot Interaction,'' in \emph{Proceedings of the 2025 ACM/IEEE International Conference on Human-Robot Interaction (HRI)}, Melbourne, Australia, March 2025, pp. 859--868.

\bibitem{lala2019}
D. Lala, K. Inoue, and T. Kawahara, ``Smooth turn-taking by a robot using an online continuous model to generate turn-taking cues,'' in \emph{Proceedings of the 2019 International Conference on Multimodal Interaction (ICMI)}, Suzhou, China, October 2019, pp. 226--234.

\bibitem{mehrabian1996}
A. Mehrabian, ``Pleasure-arousal-dominance: A general framework for describing and measuring individual differences in temperament,'' \emph{Current Psychology}, vol. 14, no. 4, pp. 261--292, December 1996.

\bibitem{marsella2009}
S. C. Marsella and J. Gratch, ``EMA: A process model of appraisal dynamics,'' \emph{Cognitive Systems Research}, vol. 10, no. 1, pp. 70--90, March 2009.

\bibitem{gebhard2005}
P. Gebhard, ``ALMA: A Layered Model of Affect,'' in \emph{Proceedings of the 4th International Joint Conference on Autonomous Agents and Multiagent Systems (AAMAS)}, Utrecht, Netherlands, July 2005, pp. 29--36.

\bibitem{ortony1988}
A. Ortony, G. L. Clore, and A. Collins, \emph{The Cognitive Structure of Emotions}. Cambridge, UK: Cambridge University Press, July 1988.

\bibitem{picard1997}
R. W. Picard, \emph{Affective Computing}. Cambridge, MA, USA: MIT Press, September 1997.

\bibitem{scherer2005}
K. R. Scherer, ``What are emotions? And how can they be measured?'' \emph{Social Science Information}, vol. 44, no. 4, pp. 695--729, December 2005.

\bibitem{anderson2004}
J. R. Anderson, D. Bothell, M. D. Byrne, S. Douglass, C. Lebiere, and Y. Qin, ``An integrated theory of the mind,'' \emph{Psychological Review}, vol. 111, no. 4, pp. 1036--1060, October 2004.

\bibitem{laird2012}
J. E. Laird, \emph{The Soar Cognitive Architecture}. Cambridge, MA, USA: MIT Press, May 2012.

\bibitem{gutierrez2024}
B. J. Guti{\'e}rrez, Y. Shu, Y. Gu, M. Yasunaga, and Y. Su, ``HippoRAG: Neurobiologically Inspired Long-Term Memory for Large Language Models,'' in \emph{Advances in Neural Information Processing Systems (NeurIPS 2024)}, vol. 37, Vancouver, BC, Canada, December 2024, pp. 59532--59569.

\bibitem{teyler1986}
T. J. Teyler and P. DiScenna, ``The hippocampal indexing theory,'' \emph{Behavioral Neuroscience}, vol. 100, no. 2, pp. 147--154, April 1986.

\bibitem{mcclelland1995}
J. L. McClelland, B. L. McNaughton, and R. C. O'Reilly, ``Why there are complementary learning systems in the hippocampus and neocortex: Insights from the successes and failures of connectionist models of learning and memory,'' \emph{Psychological Review}, vol. 102, no. 3, pp. 419--457, July 1995.

\bibitem{maruyama2016}
Y. Maruyama, S. Kato, and T. Azumi, ``Exploring the performance of ROS2,'' in \emph{Proceedings of the 13th International Conference on Embedded Software (EMSOFT)}, Pittsburgh, PA, USA, October 2016, pp. 1--10.

\bibitem{nats2019}
T. Sharvari and K. Sowmya Nag, ``A Study on Modern Messaging Systems - Kafka, RabbitMQ and NATS Streaming,'' \emph{International Journal of Computer Applications}, vol. 182, no. 41, pp. 18--22, March 2019.

\bibitem{zhang2022}
Y. Zhang, Y. Zhang, G. Portokalidis, and J. Xu, ``Towards Understanding the Runtime Performance of Rust,'' in \emph{Proceedings of the 37th IEEE/ACM International Conference on Automated Software Engineering (ASE)}, Rochester, NY, USA, October 2022, pp. 1--12.

\bibitem{krafka2016}
K. Krafka, A. Khosla, P. Kellnhofer, H. Kannan, S. Bhandarkar, W. Matusik, and A. Torralba, ``Eye Tracking for Everyone,'' in \emph{Proceedings of the IEEE Conference on Computer Vision and Pattern Recognition (CVPR)}, Las Vegas, NV, USA, June 2016, pp. 2176--2184.

\bibitem{kollias2021}
D. Kollias and S. Zafeiriou, ``Affect Analysis in-the-Wild: Valence-Arousal, Expressions, Action Units and a Unified Framework,'' \emph{arXiv preprint arXiv:2103.15792}, March 2021.

\bibitem{kusupati2022}
A. Kusupati, G. Bhatt, A. Rege, M. Wallingford, A. Sinha, V. Ramanujan, W. Howard-Snyder, K. Chen, S. Kakade, P. Jain, and A. Farhadi, ``Matryoshka Representation Learning,'' in \emph{Advances in Neural Information Processing Systems (NeurIPS 2022)}, New Orleans, LA, USA, December 2022, pp. 30233--30249.

\bibitem{easterbrook1959}
J. A. Easterbrook, ``The effect of emotion on cue utilization and the organization of behavior,'' \emph{Psychological Review}, vol. 66, no. 3, pp. 183--201, May 1959.

\bibitem{kang2024}
H. Kang, M. Ben Moussa, and N. Magnenat-Thalmann, ``Nadine: An LLM-driven Intelligent Social Robot with Affective Capabilities and Human-like Memory,'' \emph{arXiv preprint arXiv:2405.20189}, May 2024.

\bibitem{kosinski2024}
M. Kosinski, ``Evaluating large language models in theory of mind tasks,'' \emph{Proceedings of the National Academy of Sciences}, vol. 121, no. 45, p. e2405460121, November 2024.

\end{thebibliography}

\end{document}