import React, { useState, useEffect, useRef, useMemo, useCallback } from 'react';
import { api, buildAvailableSearchProviders } from '../api';
import SearchableModelSelect from './SearchableModelSelect';
import { getShortModelName } from '../utils/modelHelpers';
import { filterOAuthModels, OAUTH_PROVIDERS } from '../constants/oauthProviders';
import DocumentUpload from './DocumentUpload';
import { useI18n } from '../i18n';
import { reviewGroupName } from '../utils/reviewPresentation.js';
import { REVIEW_IDENTITIES, reviewIdentity } from '../utils/reviewIdentity.js';
import ReviewEmblem from './ReviewEmblem';
import PersonaFileImport from './PersonaFileImport.jsx';
import LocalModelConnect from './LocalModelConnect.jsx';
import { clampReviewRounds, reviewRoundPlan } from '../utils/reviewRounds.js';
import './ReviewBoard.css';
import './AdvisorSetup.css';
import './ReviewServiceTheme.css';

const MIN_ROUNDS = 1;
const MAX_ROUNDS = 10;
const MAX_PRESETS = 20;
const MAX_ADVISORS = 8;

function clampRounds(value, fallback = 3) {
  return clampReviewRounds(value,fallback);
}

function normalizePresetMode(mode) {
  return mode === 'advanced' ? 'advanced' : 'simple';
}

function buildPresetSnapshot({
  selectedPersonaIds,
  modelMode,
  chosenModel,
  tiebreakerModel,
  modelAssignments,
  rounds,
  searchProvider,
}) {
  const sortedPersonaIds = [...selectedPersonaIds].sort();
  const assignments =
    modelMode === 'advanced'
      ? Object.fromEntries(
          sortedPersonaIds
            .filter((id) => modelAssignments[id])
            .sort()
            .map((id) => [id, modelAssignments[id]])
        )
      : null;

  return {
    persona_ids: sortedPersonaIds,
    mode: modelMode,
    default_model: chosenModel || '',
    tiebreaker_model: tiebreakerModel || '',
    model_assignments: assignments && Object.keys(assignments).length > 0 ? assignments : null,
    max_rounds: rounds,
    search_provider: searchProvider,
  };
}

function snapshotsEqual(a, b) {
  if (!a || !b) return false;
  return JSON.stringify(a) === JSON.stringify(b);
}

function removePersonaFromPreset(preset, personaId) {
  const modelAssignments = preset.model_assignments == null
    ? preset.model_assignments
    : Object.fromEntries(
        Object.entries(preset.model_assignments).filter(([id]) => id !== personaId)
      );
  return {
    ...preset,
    persona_ids: (preset.persona_ids || []).filter((id) => id !== personaId),
    model_assignments: modelAssignments,
  };
}

function removePersonaFromSnapshot(snapshot, personaId) {
  if (!snapshot) return snapshot;
  const modelAssignments = snapshot.model_assignments == null
    ? null
    : Object.fromEntries(
        Object.entries(snapshot.model_assignments).filter(([id]) => id !== personaId)
      );
  return {
    ...snapshot,
    persona_ids: (snapshot.persona_ids || []).filter((id) => id !== personaId),
    model_assignments: modelAssignments && Object.keys(modelAssignments).length > 0
      ? modelAssignments
      : null,
  };
}

function newPresetId() {
  if (typeof crypto !== 'undefined' && crypto.randomUUID) {
    return crypto.randomUUID();
  }
  return `preset-${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
}

function hasAnyDirectProviderKey(settings) {
  return !!(
    settings.openai_api_key_set
    || settings.anthropic_api_key_set
    || settings.google_api_key_set
    || settings.mistral_api_key_set
    || settings.deepseek_api_key_set
    || settings.groq_api_key_set
    || settings.nvidia_api_key_set
    || settings.opencode_api_key_set
  );
}

const DIRECT_PROVIDER_KEY_FLAGS = {
  openai: 'openai_api_key_set',
  anthropic: 'anthropic_api_key_set',
  google: 'google_api_key_set',
  mistral: 'mistral_api_key_set',
  deepseek: 'deepseek_api_key_set',
  groq: 'groq_api_key_set',
  nvidia: 'nvidia_api_key_set',
  'opencode-zen': 'opencode_api_key_set',
  'opencode-go': 'opencode_api_key_set',
  // Backend returns capitalized labels with a space; allow both forms.
  'opencode zen': 'opencode_api_key_set',
  'opencode go': 'opencode_api_key_set',
};

/** Filter direct models respecting global provider toggles. */
function filterDirectModelsForAdvisor(directModels, settings) {
  const ep = settings.enabled_providers || {};
  const dt = settings.direct_provider_toggles || {};
  return directModels.filter((model) => {
    if (model.id?.startsWith('xai-oauth:') || model.id?.startsWith('openai-oauth:') || model.id?.startsWith('github-copilot:')) {
      return false;
    }
    if (model.provider === 'Groq') {
      return settings.groq_api_key_set && (ep.groq !== false);
    }
    if (!ep.direct) return false;
    const providerKey = (model.provider || '').toLowerCase().replace(/\s+/g, '-');
    if (dt[providerKey] === false) return false;
    const flag = DIRECT_PROVIDER_KEY_FLAGS[providerKey];
    return flag ? settings[flag] : false;
  });
}

/** Model sources respect global provider toggles. */
function getAdvisorModelSources(settings) {
  const ep = settings.enabled_providers || {};
  const hasOAuth = OAUTH_PROVIDERS.some(
    (p) => settings[p.connectedKey] && ep[p.id] !== false
  );
  return {
    openrouter: !!settings.openrouter_api_key_set && (ep.openrouter !== false),
    ollama: !!settings.ollama_base_url && (ep.ollama !== false),
    direct: hasAnyDirectProviderKey(settings) && (ep.direct !== false),
    custom: !!settings.custom_endpoint_url && (ep.custom !== false),
    local: !!settings.local_model_url && !!ep.local,
    oauth: hasOAuth,
  };
}

export default function AdvisorSetup({
  onStartDebate,
  isLoading = false,
}) {
  const { t } = useI18n();
  const [personas, setPersonas] = useState([]);
  const [personasLoading, setPersonasLoading] = useState(true);
  const [models, setModels] = useState([]);
  const [modelsLoading, setModelsLoading] = useState(true);
  const [selectedPersonaIds, setSelectedPersonaIds] = useState([]);
  const [chairPersonaId, setChairPersonaId] = useState('');
  const [chairError, setChairError] = useState('');
  const [modelMode, setModelMode] = useState('simple');
  const [chosenModel, setChosenModel] = useState('');
  const [tiebreakerModel, setTiebreakerModel] = useState('');
  const [modelAssignments, setModelAssignments] = useState({});
  const [rounds, setRounds] = useState(3);
  const [roundError,setRoundError]=useState('');
  const [roleFilesBusy,setRoleFilesBusy]=useState(false);
  const roundSave=useRef(Promise.resolve());
  const [editingPersona, setEditingPersona] = useState(null);
  const [isCreatingPersona, setIsCreatingPersona] = useState(false);
  const [editForm, setEditForm] = useState({ name: '', role: '', description: '', system_prompt: '', avatar_emoji: '' });
  const [editSaving, setEditSaving] = useState(false);
  const [editError, setEditError] = useState(null);
  const [searchProvider, setSearchProvider] = useState(null);
  const [availableSearchProviders, setAvailableSearchProviders] = useState([{ id: 'duckduckgo', name: 'DuckDuckGo' }]);
  const [searchPopoverOpen, setSearchPopoverOpen] = useState(false);
  const searchPopoverRef = useRef(null);
  const [question, setQuestion] = useState('');
  const [documentPayload, setDocumentPayload] = useState({ documents: [], attachments: [], warnings: [] });
  const [documentsBusy, setDocumentsBusy] = useState(false);
  const [documentResetKey, setDocumentResetKey] = useState(0);
  const [personasExpanded, setPersonasExpanded] = useState(false);
  const [modelsExpanded, setModelsExpanded] = useState(false);
  const modelSectionRef = useRef(null);
  const [presets, setPresets] = useState([]);
  const [activePresetId, setActivePresetId] = useState(null);
  const [presetPopoverOpen, setPresetPopoverOpen] = useState(false);
  const [saveModalOpen, setSaveModalOpen] = useState(false);
  const [saveForm, setSaveForm] = useState({
    name: '',
    isDefault: false,
    includeConfig: true,
    updateExisting: true,
  });
  const [presetSaving, setPresetSaving] = useState(false);
  const presetPopoverRef = useRef(null);
  const loadedSnapshotRef = useRef(null);
  const applyLocalModel = useCallback(value=>{
    setModels(previous=>Array.from(new Map([...previous,...value.models].map(m=>[m.id,m])).values()));
    setChosenModel(value.model);setTiebreakerModel(value.model);setModelMode('simple');setActivePresetId(null);
  },[]);
  useEffect(()=>{
    const apply=event=>applyLocalModel(event.detail);
    window.addEventListener('review-local-model-connected',apply);
    return ()=>window.removeEventListener('review-local-model-connected',apply);
  },[applyLocalModel]);

  useEffect(() => {
    const handleClickOutside = (e) => {
      if (searchPopoverRef.current && !searchPopoverRef.current.contains(e.target)) {
        setSearchPopoverOpen(false);
      }
      if (presetPopoverRef.current && !presetPopoverRef.current.contains(e.target)) {
        setPresetPopoverOpen(false);
      }
    };
    if (searchPopoverOpen || presetPopoverOpen) {
      document.addEventListener('mousedown', handleClickOutside);
    }
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [searchPopoverOpen, presetPopoverOpen]);

  useEffect(() => {
    const fetchModels = async () => {
      try {
        const [personasResult, settings] = await Promise.all([
          api.getPersonas().catch(() => []),
          api.getSettings(),
        ]);
        setPersonas(personasResult);
        setChairPersonaId(settings.advisor_chair_persona_id || '');

        setAvailableSearchProviders(buildAvailableSearchProviders(settings));

        const loadSources = getAdvisorModelSources(settings);
        const ollamaUrl = settings.ollama_base_url || 'http://localhost:11434';

        const [orModels, ollamaModels, directModels, customModels, oauthModels, localModels] = await Promise.all([
          loadSources.openrouter
            ? api.getModels().then(d => d.models || []).catch(() => [])
            : [],
          loadSources.ollama
            ? api.getOllamaModels(ollamaUrl).then(d => (d.models || []).map(m => ({
                ...m,
                id: m.id.startsWith('ollama:') ? m.id : `ollama:${m.id}`,
                name: `${m.name || m.id} (Local)`,
                provider: 'Ollama',
              }))).catch(() => [])
            : [],
          loadSources.direct
            ? api.getDirectModels()
              .then(d => filterDirectModelsForAdvisor(Array.isArray(d) ? d : (d.models || []), settings))
              .catch(() => [])
            : [],
          loadSources.custom
            ? api.getCustomEndpointModels().then(d => d.models || []).catch(() => [])
            : [],
          loadSources.oauth
            ? api.getDirectModels()
              .then(d => filterOAuthModels(Array.isArray(d) ? d : (d.models || []), settings))
              .catch(() => [])
            : [],
          loadSources.local ? api.localModels().then(d=>d.models || []).catch(()=>[]) : [],
        ]);

        const combined = [...orModels, ...ollamaModels, ...directModels, ...customModels, ...oauthModels, ...localModels];
        const unique = new Map();
        combined.forEach(m => unique.set(m.id, m));
        const sorted = Array.from(unique.values())
          .sort((a, b) => (a.name || '').localeCompare(b.name || ''));

        setModels(sorted);

        const loadedPresets = Array.isArray(settings.advisor_presets) ? settings.advisor_presets : [];
        setPresets(loadedPresets);

        let initialModel = settings.advisor_default_model || (sorted.length > 0 ? sorted[0].id : '');
        let initialTiebreaker = settings.advisor_tiebreaker_model || initialModel;
        const initialRounds = clampRounds(settings.advisor_default_rounds);

        setChosenModel(initialModel);
        setTiebreakerModel(initialTiebreaker);
        setRounds(initialRounds);

        const defaultPreset = loadedPresets.find((p) => p.is_default) || null;
        if (defaultPreset) {
          const personaIds = (defaultPreset.persona_ids || []).filter(id => id !== settings.advisor_chair_persona_id).slice(0, MAX_ADVISORS);
          const mode = normalizePresetMode(defaultPreset.mode);
          if (defaultPreset.default_model) {
            initialModel = defaultPreset.default_model;
            setChosenModel(defaultPreset.default_model);
          }
          if (defaultPreset.tiebreaker_model) {
            initialTiebreaker = defaultPreset.tiebreaker_model;
            setTiebreakerModel(defaultPreset.tiebreaker_model);
          } else if (defaultPreset.default_model) {
            initialTiebreaker = defaultPreset.default_model;
            setTiebreakerModel(defaultPreset.default_model);
          }
          const modelAssignmentsForPreset =
            mode === 'advanced' && defaultPreset.model_assignments
              ? { ...defaultPreset.model_assignments }
              : {};
          // The last saved round choice takes priority on opening; explicitly
          // selecting a preset below can still apply that preset's round count.

          setSelectedPersonaIds(personaIds);
          setModelMode(mode);
          setModelAssignments(modelAssignmentsForPreset);
          setSearchProvider(defaultPreset.search_provider ?? null);
          setActivePresetId(defaultPreset.id);
          loadedSnapshotRef.current = buildPresetSnapshot({
            selectedPersonaIds: personaIds,
            modelMode: mode,
            chosenModel: initialModel,
            tiebreakerModel: initialTiebreaker,
            modelAssignments: modelAssignmentsForPreset,
            rounds: clampRounds(defaultPreset.max_rounds ?? initialRounds,initialRounds),
            searchProvider: defaultPreset.search_provider ?? null,
          });
        }
        setModelsExpanded(defaultPreset?.mode === 'advanced'
          ? (defaultPreset.persona_ids || []).some(id=>!defaultPreset.model_assignments?.[id])
          : !initialModel);
      } catch (err) {
        console.error('Failed to load advisor models:', err);
      } finally {
        setPersonasLoading(false);
        setModelsLoading(false);
      }
    };

    fetchModels();
  }, []);

  // ── Helpers ──────────────────────────────────────────────────────────────

  const togglePersona = (id) => {
    setSelectedPersonaIds((prev) => {
      if (prev.includes(id)) {
        return prev.filter((x) => x !== id);
      }
      if (prev.length >= MAX_ADVISORS || id === chairPersonaId) return prev;
      return [...prev, id];
    });
  };

  const persistAdvisorSetting = async (field, value, setter) => {
    setter(value);
    try {
      const currentSettings = await api.getSettings();
      await api.updateSettings({ ...currentSettings, [field]: value });
    } catch (err) {
      console.error(`Failed to auto-save ${field}:`, err);
    }
  };

  const handleSimpleModelChange = (modelId) => {
    persistAdvisorSetting('advisor_default_model', modelId, setChosenModel);
  };

  const handleModelAssignment = (personaId, modelId) => {
    setModelAssignments((prev) => ({ ...prev, [personaId]: modelId }));
  };

  const handleTiebreakerModelChange = (modelId) => {
    persistAdvisorSetting('advisor_tiebreaker_model', modelId, setTiebreakerModel);
  };

  const handleRoundsChange = useCallback(value => {
    const next=clampRounds(value,3);
    setRounds(next);setRoundError('');
    // Serialize quick clicks so an older save cannot overwrite the last choice.
    roundSave.current=roundSave.current.catch(()=>{}).then(()=>api.updateSettings({advisor_default_rounds:next})).then(()=>setRoundError('')).catch(()=>setRoundError('轮数暂未保存，下次新建可能恢复旧值。'));
  },[]);

  const currentSnapshot = useMemo(
    () => buildPresetSnapshot({
      selectedPersonaIds,
      modelMode,
      chosenModel,
      tiebreakerModel,
      modelAssignments,
      rounds,
      searchProvider,
    }),
    [selectedPersonaIds, modelMode, chosenModel, tiebreakerModel, modelAssignments, rounds, searchProvider]
  );

  const isPresetDirty = activePresetId != null && !snapshotsEqual(currentSnapshot, loadedSnapshotRef.current);

  const activePreset = useMemo(
    () => presets.find((p) => p.id === activePresetId) || null,
    [presets, activePresetId]
  );

  const persistPresets = async (nextPresets) => {
    await api.updateSettings({ advisor_presets: nextPresets });
    setPresets(nextPresets);
  };

  const applyPresetToForm = useCallback((preset, { markClean = true, touchLastUsed = true } = {}) => {
    const personaIds = (preset.persona_ids || []).filter(id => id !== chairPersonaId).slice(0, MAX_ADVISORS);
    const mode = normalizePresetMode(preset.mode);
    const nextModel = preset.default_model || chosenModel;
    const nextTiebreaker = preset.tiebreaker_model || preset.default_model || tiebreakerModel;
    const nextAssignments =
      mode === 'advanced' && preset.model_assignments
        ? { ...preset.model_assignments }
        : {};
    const nextRounds = preset.max_rounds ? clampRounds(preset.max_rounds) : rounds;
    const nextSearchProvider = preset.search_provider ?? null;

    setSelectedPersonaIds(personaIds);
    setModelMode(mode);
    if (preset.default_model) setChosenModel(nextModel);
    if (preset.tiebreaker_model) setTiebreakerModel(nextTiebreaker);
    else if (preset.default_model) setTiebreakerModel(nextTiebreaker);
    setModelAssignments(nextAssignments);
    if (preset.max_rounds) handleRoundsChange(nextRounds);
    setSearchProvider(nextSearchProvider);
    setActivePresetId(preset.id);
    setPresetPopoverOpen(false);

    if (markClean) {
      loadedSnapshotRef.current = buildPresetSnapshot({
        selectedPersonaIds: personaIds,
        modelMode: mode,
        chosenModel: nextModel,
        tiebreakerModel: nextTiebreaker,
        modelAssignments: nextAssignments,
        rounds: nextRounds,
        searchProvider: nextSearchProvider,
      });
    }

    if (touchLastUsed) {
      const now = new Date().toISOString();
      const nextPresets = presets.map((p) => (
        p.id === preset.id ? { ...p, last_used_at: now } : p
      ));
      persistPresets(nextPresets).catch((err) => {
        console.error('Failed to update preset last used:', err);
      });
    }
  }, [chosenModel, tiebreakerModel, rounds, presets, chairPersonaId, handleRoundsChange]);

  const handleSelectCustomSetup = () => {
    setActivePresetId(null);
    loadedSnapshotRef.current = null;
    setPresetPopoverOpen(false);
  };

  const openSavePresetModal = () => {
    setSaveForm({
      name: activePreset?.name || '',
      isDefault: activePreset?.is_default || presets.length === 0,
      includeConfig: true,
      updateExisting: Boolean(activePresetId),
    });
    setSaveModalOpen(true);
    setPresetPopoverOpen(false);
  };

  const closeSavePresetModal = () => {
    setSaveModalOpen(false);
    setPresetSaving(false);
  };

  const buildPresetFromForm = (id, name, { isDefault, includeConfig }) => ({
    id,
    name: name.trim(),
    persona_ids: selectedPersonaIds,
    mode: modelMode,
    default_model: chosenModel || '',
    tiebreaker_model: tiebreakerModel || chosenModel || '',
    model_assignments: modelMode === 'advanced' ? currentSnapshot.model_assignments : null,
    max_rounds: includeConfig ? rounds : MIN_ROUNDS,
    search_provider: includeConfig ? searchProvider : null,
    is_default: isDefault,
    last_used_at: new Date().toISOString(),
  });

  const handleSavePreset = async () => {
    const name = saveForm.name.trim();
    if (!name || presetSaving) return;

    setPresetSaving(true);
    try {
      let nextPresets = [...presets];
      const shouldUpdate = saveForm.updateExisting && activePresetId;

      if (shouldUpdate) {
        nextPresets = nextPresets.map((p) => {
          if (p.id === activePresetId) {
            return buildPresetFromForm(p.id, name, saveForm);
          }
          if (saveForm.isDefault) {
            return { ...p, is_default: false };
          }
          return p;
        });
      } else {
        const id = newPresetId();
        const newPreset = buildPresetFromForm(id, name, saveForm);
        nextPresets = [
          newPreset,
          ...(saveForm.isDefault ? presets.map((p) => ({ ...p, is_default: false })) : presets),
        ].slice(0, MAX_PRESETS);
        setActivePresetId(id);
      }

      await persistPresets(nextPresets);
      loadedSnapshotRef.current = currentSnapshot;
      closeSavePresetModal();
    } catch (err) {
      console.error('Failed to save advisor preset:', err);
      setPresetSaving(false);
    }
  };

  const handleDeletePreset = async (presetId) => {
    try {
      const nextPresets = presets.filter((p) => p.id !== presetId);
      await persistPresets(nextPresets);
      if (activePresetId === presetId) {
        setActivePresetId(null);
        loadedSnapshotRef.current = null;
      }
      setPresetPopoverOpen(false);
    } catch (err) {
      console.error('Failed to delete advisor preset:', err);
    }
  };

  const handleSetDefaultPreset = async (presetId) => {
    try {
      const nextPresets = presets.map((p) => ({
        ...p,
        is_default: p.id === presetId,
      }));
      await persistPresets(nextPresets);
    } catch (err) {
      console.error('Failed to set default preset:', err);
    }
  };

  const modelSummaryLine = useMemo(() => {
    if (selectedPersonaIds.length === 0) return null;
    const names = selectedPersonaIds
      .map((id) => personas.find((p) => p.id === id)?.name)
      .filter(Boolean);
    if (names.length === 0) return null;

    if (modelMode === 'simple' && chosenModel) {
      return `${names.join(' · ')} → ${getShortModelName(chosenModel)}`;
    }

    if (modelMode === 'advanced') {
      const parts = selectedPersonaIds.map((id) => {
        const persona = personas.find((p) => p.id === id);
        const model = modelAssignments[id];
        if (!persona || !model) return null;
        return `${persona.name} → ${getShortModelName(model)}`;
      }).filter(Boolean);
      if (parts.length === 0) return null;
      return parts.join(' · ');
    }

    return null;
  }, [selectedPersonaIds, personas, modelMode, chosenModel, modelAssignments]);

  const BLANK_PERSONA_FORM = { name: '', role: '', description: '', system_prompt: '', avatar_emoji: '' };

  const openEditModal = (e, persona) => {
    e.stopPropagation();
    setIsCreatingPersona(false);
    setEditError(null);
    setEditingPersona(persona);
    setEditForm({
      name: persona.name,
      role: persona.role,
      description: persona.description,
      system_prompt: persona.system_prompt,
      avatar_emoji: persona.avatar_emoji,
    });
  };

  const openCreateModal = () => {
    setIsCreatingPersona(true);
    setEditError(null);
    setEditingPersona({ avatar_emoji: '🧑‍💼', is_custom: true });
    setEditForm(BLANK_PERSONA_FORM);
  };

  const closeEditModal = () => {
    setEditingPersona(null);
    setIsCreatingPersona(false);
    setEditSaving(false);
    setEditError(null);
  };

  const runEditAction = async (apiFn, errorMsg) => {
    if (!editingPersona || editSaving) return;
    setEditSaving(true);
    setEditError(null);
    try {
      const result = await apiFn();
      if (result) {
        setPersonas((prev) => prev.map((p) => p.id === result.id ? result : p));
      }
      closeEditModal();
    } catch (err) {
      console.error(errorMsg, err);
      setEditError(err.message || t(errorMsg));
      setEditSaving(false);
    }
  };

  const handleEditSave = () => {
    if (isCreatingPersona) {
      if (!editForm.name.trim() || !editForm.role.trim() || !editForm.system_prompt.trim()) {
        setEditError(t('Name, role, and system prompt are required.'));
        return;
      }
      return runEditAction(
        async () => {
          const created = await api.createPersona(editForm);
          setPersonas((prev) => [...prev, created]);
          return null;
        },
        'Failed to create advisor:'
      );
    }
    return runEditAction(
      () => api.updatePersona(editingPersona.id, editForm),
      'Failed to save persona:'
    );
  };

  const handleEditReset = () => runEditAction(
    () => api.resetPersona(editingPersona.id),
    'Failed to reset persona:'
  );

  const handleEditDelete = () => {
    if (!editingPersona || editSaving) return;
    if (!window.confirm(t('Delete {advisor}? Saved presets will remove this advisor.', { advisor: editingPersona.name || t('this advisor') }))) {
      return;
    }

    return runEditAction(
      async () => {
        const deletedId = editingPersona.id;
        const nextSelectedPersonaIds = selectedPersonaIds.filter((id) => id !== deletedId);
        const nextModelAssignments = Object.fromEntries(
          Object.entries(modelAssignments).filter(([id]) => id !== deletedId)
        );
        const nextPresets = presets.map((preset) => removePersonaFromPreset(preset, deletedId));

        await api.deletePersona(deletedId);
        if (chairPersonaId === deletedId) setChairPersonaId('');
        setPersonas((prev) => prev.filter((p) => p.id !== deletedId));
        setSelectedPersonaIds(nextSelectedPersonaIds);
        setModelAssignments(nextModelAssignments);
        setPresets(nextPresets);
        if (activePresetId) {
          const activePreset = presets.find((preset) => preset.id === activePresetId);
          if (activePreset?.persona_ids?.includes(deletedId)) {
            loadedSnapshotRef.current = removePersonaFromSnapshot(
              loadedSnapshotRef.current,
              deletedId
            );
          }
        }
        return null;
      },
      'Failed to delete advisor:'
    );
  };

  const canStart =
    selectedPersonaIds.length >= 2 &&
    (modelMode === 'simple' ? !!chosenModel : selectedPersonaIds.every((id) => !!modelAssignments[id])) &&
    question.trim().length > 0 &&
    !documentsBusy && !roleFilesBusy;

  const getHint = () => {
    if (canStart) return t('↵ Enter to start · Shift+Enter for new line');
    if (question.trim().length === 0) return t('Fill in the form below, then start your debate');
    if (selectedPersonaIds.length < 2) return t('⚠ Select at least 2 advisors below');
    if (modelMode === 'simple' && !chosenModel) return t('⚠ Choose a model below');
    return t('⚠ Assign a model to each advisor');
  };

  const handleSubmit = () => {
    if (!canStart || isLoading) return;
    const payload = {
      question: question.trim(),
      personaIds: selectedPersonaIds,
      reviewPersonas: selectedPersonaIds.map(id => personas.find(p => p.id === id)).filter(Boolean),
      defaultModel: chosenModel,
      tiebreakerModel: modelMode === 'simple' ? chosenModel : (tiebreakerModel || null),
      modelAssignments: modelMode === 'advanced' ? modelAssignments : null,
      maxRounds: rounds,
      roundPolicy: 'fixed',
      searchProvider,
      documents: documentPayload.documents || [],
      attachments: documentPayload.attachments || [],
    };
    onStartDebate(payload);
    setDocumentPayload({ documents: [], attachments: [], warnings: [] });
    setDocumentResetKey((key) => key + 1);
  };

  // ── Render ───────────────────────────────────────────────────────────────

  const selectedCount = selectedPersonaIds.length;
  const showPersonas = personasExpanded || (!personasLoading && selectedCount < 2);
  const modelNeedsAttention = !modelsLoading && (modelMode === 'simple' ? !chosenModel : selectedPersonaIds.some(id=>!modelAssignments[id]));
  const modelLabel = modelsLoading ? '正在读取模型' : modelMode === 'simple' ? chosenModel ? getShortModelName(chosenModel) : '请先选择模型' : '各团分别配置';
  const openModelSettings = () => { setModelsExpanded(true);modelSectionRef.current?.scrollIntoView({block:'nearest',behavior:'smooth'}); };

  return (
    <div className="advisor-setup service-setup">
      <header className="review-setup-header ip-hero">
        <div className="ip-hero__copy"><span className="ip-hero__brand"><strong>Git源宝</strong><span>审稿室</span></span><h1>开始本次审稿</h1><p>放入稿件，确认审阅安排。各团细读，主编给出结论与修改方向。</p></div>
        <div className="ip-hero__art" aria-hidden="true"><i className="ip-shape ip-shape--yellow"/><i className="ip-shape ip-shape--blue"/><i className="ip-shape ip-shape--red"/><img src="/yuanbao-ip-cat-512.png" alt="" width="256" height="256" fetchPriority="high"/><span className="ip-hero__seal">小猫在场，认真开讲。</span></div>
      </header>
      <div className="ip-compose">
      {/* Question Textarea + Start Debate — primary input card */}
      <div className="advisor-setup__section advisor-setup__question-card">
        <label className="advisor-setup__section-label" htmlFor="advisor-question">
          放入稿件
        </label>
        <textarea
          id="advisor-question"
          className="advisor-setup__question"
          placeholder="粘贴需要审阅的稿件，也可以补充目标读者、文稿用途和你最想解决的问题。"
          rows={4}
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
              e.preventDefault();
              handleSubmit();
            }
          }}
        />
        <DocumentUpload
          disabled={isLoading}
          resetKey={documentResetKey}
          onChange={setDocumentPayload}
          onBusyChange={setDocumentsBusy}
        />
        <div className="advisor-setup__question-footer">
          <span className="advisor-setup__question-hint">
            {getHint()}
          </span>
          <button
            type="button"
            className={`advisor-setup__start-btn advisor-setup__start-btn--inline ${canStart && !isLoading ? 'advisor-setup__start-btn--ready' : ''}`}
            onClick={handleSubmit}
            disabled={!canStart || isLoading}
          >
            {isLoading ? (
              <><span className="advisor-setup__spinner" aria-hidden="true" /> {t('Starting…')}</>
            ) : (
              t('Start Debate ➤')
            )}
          </button>
        </div>
      </div>

      <div className="ip-compose__options"><h2>本次审阅安排</h2>
      <div className="setup-current-model"><span>使用模型</span><strong>{modelLabel}</strong><button type="button" onClick={openModelSettings}>{modelNeedsAttention ? '选择模型' : '调整'}</button></div>
      <div className="setup-current-teams"><span>参与评审</span><div>{selectedPersonaIds.map(id=>{const p=personas.find(item=>item.id===id);return p ? <span key={id} title={p.name}><ReviewEmblem persona={p} compact/><small>{reviewIdentity(p).label}</small></span> : null;})}</div><p>{selectedCount} 团独立审阅，主编最后汇总</p></div>
      {/* Rounds + Web Search — grouped beside the manuscript. */}
      <div className="advisor-setup__section">
        <div className="advisor-setup__config-row">
          <div className="advisor-setup__rounds">
            <span className="advisor-setup__config-label">审阅轮数</span>
            <div className="advisor-setup__stepper">
              <button
                type="button"
                className="advisor-setup__stepper-btn"
                onClick={() => handleRoundsChange(rounds-1)}
                disabled={rounds <= MIN_ROUNDS || isLoading}
                aria-label={t('Decrease rounds')}
              >
                −
              </button>
              <span className="advisor-setup__stepper-value">{rounds}</span>
              <button
                type="button"
                className="advisor-setup__stepper-btn"
                onClick={() => handleRoundsChange(rounds+1)}
                disabled={rounds >= MAX_ROUNDS || isLoading}
                aria-label={t('Increase rounds')}
              >
                +
              </button>
            </div>
            <div className="review-round-presets">{[[1,'快审'],[2,'复核'],[3,'深入']].map(([n,label])=><button key={n} type="button" aria-pressed={rounds===n} disabled={isLoading} onClick={()=>handleRoundsChange(n)}>{n}轮{label}</button>)}</div>
          </div>

          <div className="advisor-setup__websearch-picker" ref={searchPopoverRef}>
            <span className="advisor-setup__config-label">{t('Web Search')}</span>
            <button
              type="button"
              className={`advisor-setup__search-btn ${searchProvider ? 'advisor-setup__search-btn--active' : ''}`}
              onClick={() => setSearchPopoverOpen((v) => !v)}
              aria-haspopup="listbox"
              aria-expanded={searchPopoverOpen}
            >
              <span>🌐</span>
              <span>{searchProvider ? (availableSearchProviders.find(p => p.id === searchProvider)?.name || searchProvider) : t('Off')}</span>
              <span className="advisor-setup__search-chevron">›</span>
            </button>
            {searchPopoverOpen && (
              <div className="advisor-setup__search-popover" role="listbox">
                <button
                  type="button"
                  className={`advisor-setup__search-option ${!searchProvider ? 'advisor-setup__search-option--selected' : ''}`}
                  onClick={() => { setSearchProvider(null); setSearchPopoverOpen(false); }}
                >
                  <span>✕</span> {t('Off')}
                </button>
                {availableSearchProviders.map((p) => (
                  <button
                    key={p.id}
                    type="button"
                    className={`advisor-setup__search-option ${searchProvider === p.id ? 'advisor-setup__search-option--selected' : ''}`}
                    onClick={() => { setSearchProvider(p.id); setSearchPopoverOpen(false); }}
                  >
                    <span>🌐</span> {p.name}
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>

      <div className="review-round-plan"><strong>{reviewRoundPlan(rounds)}</strong><p>每轮各团都会审阅，最后由主编汇总。建议先用1–2轮；更多轮会增加等待和费用。</p>{roundError && <p role="alert">{roundError}</p>}</div>
      </div></div>

      {/* Model Assignment */}
      <details className="setup-config" ref={modelSectionRef} open={modelsExpanded} onToggle={event=>setModelsExpanded(event.currentTarget.open)}>
      <summary><span><strong>模型连接与高级配置</strong><small>{modelLabel}</small></span><i aria-hidden="true">＋</i></summary>
      <div className="advisor-setup__section setup-model-body">
        <LocalModelConnect disabled={isLoading || modelsLoading} onConnected={applyLocalModel}/>
        <div className="advisor-setup__section-header">
          <span className="advisor-setup__section-label">{t('Model Assignment')}</span>
          <div className="advisor-setup__mode-tabs">
            <button
              type="button"
              className={`advisor-setup__mode-tab ${modelMode === 'simple' ? 'advisor-setup__mode-tab--active' : ''}`}
              onClick={() => setModelMode('simple')}
            >
              {t('Simple')}
            </button>
            <button
              type="button"
              className={`advisor-setup__mode-tab ${modelMode === 'advanced' ? 'advisor-setup__mode-tab--active' : ''}`}
              onClick={() => setModelMode('advanced')}
            >
              {t('Advanced')}
            </button>
          </div>
        </div>

        <div className="advisor-setup__preset-row">
          <div className="advisor-setup__preset-picker" ref={presetPopoverRef}>
            <button
              type="button"
              className="advisor-setup__preset-btn"
              onClick={() => setPresetPopoverOpen((v) => !v)}
              aria-haspopup="listbox"
              aria-expanded={presetPopoverOpen}
            >
              <span className="advisor-setup__preset-btn-icon" aria-hidden="true">📁</span>
              <span className="advisor-setup__preset-btn-label">
                {activePreset ? activePreset.name : t('Custom setup')}
              </span>
              <span className="advisor-setup__preset-chevron">›</span>
            </button>
            {presetPopoverOpen && (
              <div className="advisor-setup__preset-popover" role="listbox">
                <button
                  type="button"
                  className={`advisor-setup__preset-option ${!activePresetId ? 'advisor-setup__preset-option--selected' : ''}`}
                  onClick={handleSelectCustomSetup}
                >
                  {t('Custom setup')}
                </button>
                {presets.length === 0 ? (
                  <div className="advisor-setup__preset-empty">{t('No saved presets yet')}</div>
                ) : (
                  presets.map((preset) => (
                    <div key={preset.id} className="advisor-setup__preset-option-row">
                      <button
                        type="button"
                        className={`advisor-setup__preset-option ${activePresetId === preset.id ? 'advisor-setup__preset-option--selected' : ''}`}
                        onClick={() => applyPresetToForm(preset)}
                      >
                        {preset.is_default && <span className="advisor-setup__preset-star" aria-hidden="true">⭐</span>}
                        <span>{preset.name}</span>
                      </button>
                      <div className="advisor-setup__preset-option-actions">
                        {!preset.is_default && (
                          <button
                            type="button"
                            className="advisor-setup__preset-action-btn"
                            title={t('Set as default')}
                            aria-label={t('Set {name} as default', { name: preset.name })}
                            onClick={() => handleSetDefaultPreset(preset.id)}
                          >
                            ☆
                          </button>
                        )}
                        <button
                          type="button"
                          className="advisor-setup__preset-action-btn advisor-setup__preset-action-btn--delete"
                          title={t('Delete preset')}
                          aria-label={t('Delete {name}', { name: preset.name })}
                          onClick={() => handleDeletePreset(preset.id)}
                        >
                          ✕
                        </button>
                      </div>
                    </div>
                  ))
                )}
                <div className="advisor-setup__preset-popover-footer">
                  <button
                    type="button"
                    className="advisor-setup__preset-footer-btn"
                    onClick={openSavePresetModal}
                  >
                    {t('Save current as…')}
                  </button>
                </div>
              </div>
            )}
          </div>
          {(isPresetDirty || !activePresetId) && (
            <button
              type="button"
              className="advisor-setup__preset-save-link"
              onClick={openSavePresetModal}
            >
              {t('Save preset…')}
            </button>
          )}
        </div>

        {!modelsLoading && models.length === 0 && (
          <p className="advisor-setup__model-empty">
            {t('No models available. Add and test API keys in Settings → LLM API Keys (Ollama URL, NVIDIA, OpenRouter, etc.).')}
          </p>
        )}

        {modelSummaryLine && (
          <p className="advisor-setup__model-summary">{modelSummaryLine}</p>
        )}
        {isPresetDirty && (
          <p className="advisor-setup__preset-dirty">{t('Unsaved changes from preset')}</p>
        )}

        {modelMode === 'simple' ? (
          <div className="advisor-setup__model-simple">
            <label className="advisor-setup__model-label">
              {t('All advisors and the verdict/tiebreaker use the same model')}
            </label>
            <SearchableModelSelect
              appearance="paper"
              models={models}
              value={chosenModel}
              onChange={handleSimpleModelChange}
              placeholder={modelsLoading ? t('Loading models…') : t('Search {count} models…', { count: models.length })}
              isLoading={modelsLoading}
              isDisabled={modelsLoading}
            />
          </div>
        ) : (
          <div className="advisor-setup__model-advanced">
            {selectedPersonaIds.length === 0 ? (
              <p className="advisor-setup__model-advanced-empty">
                {t('Select at least one advisor above to assign models.')}
              </p>
            ) : (
              selectedPersonaIds.map((id) => {
                const persona = personas.find((p) => p.id === id);
                if (!persona) return null;
                return (
                  <div key={id} className="advisor-setup__model-row">
                    <span className="advisor-setup__model-row-persona">
                      <ReviewEmblem persona={persona}/>
                      <span>{persona.name}</span>
                    </span>
                    <SearchableModelSelect
                      appearance="paper"
                      models={models}
                      value={modelAssignments[id] || ''}
                      onChange={(modelId) => handleModelAssignment(id, modelId)}
                      placeholder={modelsLoading ? t('Loading…') : t('Search models…')}
                      isLoading={modelsLoading}
                      isDisabled={modelsLoading}
                    />
                  </div>
                );
              })
            )}
            <div className="advisor-setup__model-row advisor-setup__model-row--verdict">
              <span className="advisor-setup__model-row-persona">
                <span>⚖️</span>
                <span>{t('Verdict / Tiebreaker')}</span>
              </span>
              <SearchableModelSelect
                appearance="paper"
                models={models}
                value={tiebreakerModel || ''}
                onChange={handleTiebreakerModelChange}
                placeholder={modelsLoading ? t('Loading…') : t('Search models…')}
                isLoading={modelsLoading}
                isDisabled={modelsLoading}
              />
            </div>
          </div>
        )}
      </div></details>

      {/* Persona Gallery */}
      <div className="advisor-setup__section setup-personas">
        <button
          type="button"
          className="advisor-setup__section-header advisor-setup__section-header--collapsible"
          onClick={() => setPersonasExpanded((v) => !v)}
          aria-expanded={showPersonas}
        >
          <span className="advisor-setup__section-label">评审团与主编<span className="setup-personas__hint">管理角色与导入人设</span></span>
          <div className="advisor-setup__section-header-right">
            <span className={`advisor-setup__count-badge ${selectedCount >= 2 ? 'advisor-setup__count-badge--valid' : ''}`}>
              {t('{count} / 8 selected', { count: selectedCount })}
            </span>
            <span className={`advisor-setup__chevron ${showPersonas ? '' : 'advisor-setup__chevron--collapsed'}`}>
              ›
            </span>
          </div>
        </button>

        <div className={`advisor-setup__collapsible ${showPersonas ? 'advisor-setup__collapsible--open' : ''}`}>
          <div className="advisor-setup__collapsible-inner">
            <div style={{ padding: '16px', borderBottom: '1px solid var(--border-color, #334155)' }}>
              <label htmlFor="review-chair-persona" className="review-chair-label"><ReviewEmblem persona={personas.find(p => p.id === chairPersonaId) || {name:'主编'}}/><span>汇总主编<small>核对依据，整理优先级</small></span></label>
              <select id="review-chair-persona" className="select-input" value={chairPersonaId}
                style={{ display: 'block', width: '100%', marginTop: '8px' }}
                onChange={async event => {
                  const value = event.target.value;
                  try {
                    await api.updateSettings({ advisor_chair_persona_id: value });
                    setChairPersonaId(value);
                    setSelectedPersonaIds(ids => ids.filter(id => id !== value));
                    setChairError('');
                  } catch { setChairError('主编设置未保存，请重试。'); }
                }}>
                <option value="">使用默认汇总提示词</option>
                {personas.map(persona => <option key={persona.id} value={persona.id}>{persona.name}</option>)}
              </select>
              {chairPersonaId && <button type="button" className="advisor-setup__preset-footer-btn" style={{ marginTop: '8px' }}
                onClick={() => { const persona = personas.find(item => item.id === chairPersonaId); if (persona) { setEditingPersona(persona); setEditForm({ ...persona }); setIsCreatingPersona(false); setEditError(null); } }}>编辑主编设定</button>}
              {chairError && <p role="alert">{chairError}</p>}
            </div>
            <PersonaFileImport personas={personas} disabled={isLoading || personasLoading} onManual={openCreateModal} onBusyChange={setRoleFilesBusy} onImported={created=>{
              setPersonas(prev=>[...prev,...created]);
              setSelectedPersonaIds(prev=>[...prev,...created.map(p=>p.id)].slice(0,MAX_ADVISORS));
            }}/>

            {personasLoading ? (
              <div className="advisor-setup__personas-loading">{t('Loading advisors...')}</div>
            ) : (
              <div className="advisor-setup__persona-gallery">
                {personas.filter(persona => persona.id !== chairPersonaId).sort((a, b) => Number((activePreset?.persona_ids || []).includes(b.id)) - Number((activePreset?.persona_ids || []).includes(a.id)) || Number(b.is_custom) - Number(a.is_custom)).map((persona) => {
                  const selected = selectedPersonaIds.includes(persona.id);
                  return (
                    <div
                      key={persona.id}
                      role="button"
                      tabIndex={!selected && selectedCount >= MAX_ADVISORS ? -1 : 0}
                      className={`advisor-setup__persona-card ${selected ? 'advisor-setup__persona-card--selected' : ''} ${!selected && selectedCount >= MAX_ADVISORS ? 'advisor-setup__persona-card--disabled' : ''} ${persona.is_customized ? 'advisor-setup__persona-card--customized' : ''}`}
                      onClick={() => togglePersona(persona.id)}
                      onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); togglePersona(persona.id); } }}
                      style={selected ? { '--persona-color': persona.color } : {}}
                      aria-pressed={selected}
                    >
                      <button
                        type="button"
                        className="advisor-setup__persona-edit-btn"
                        onClick={(e) => openEditModal(e, persona)}
                        title={t('Edit persona')}
                        aria-label={t('Edit {name}', { name: persona.name })}
                        tabIndex={0}
                      >
                        ✏️
                      </button>
                      <ReviewEmblem persona={persona}/>
                      <span className="advisor-setup__persona-name">{reviewGroupName(persona)}</span>
                      <span className="advisor-setup__persona-role">{reviewIdentity(persona).focus}</span>
                      <span className="advisor-setup__persona-desc">{/自然短评在前/.test(persona.description || '') ? reviewIdentity(persona).summary || persona.description : persona.description}</span>
                      {persona.is_customized && (
                        <span className="advisor-setup__persona-custom-badge" title={t('Customized')}>✦</span>
                      )}
                      {selected && (
                        <span className="advisor-setup__persona-check">
                          ✓
                        </span>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Save Preset Modal */}
      {saveModalOpen && (
        <div className="advisor-setup__edit-overlay" onClick={closeSavePresetModal}>
          <div className="advisor-setup__edit-modal advisor-setup__edit-modal--compact" onClick={(e) => e.stopPropagation()}>
            <div className="advisor-setup__edit-header">
              <span className="advisor-setup__edit-emoji">📁</span>
              <span className="advisor-setup__edit-title">{t('Save Preset')}</span>
              <button type="button" className="advisor-setup__edit-close" onClick={closeSavePresetModal} aria-label={t('Close')}>✕</button>
            </div>

            <div className="advisor-setup__edit-body">
              <label className="advisor-setup__edit-field">
                <span className="advisor-setup__edit-label">{t('Preset Name')}</span>
                <input
                  type="text"
                  className="advisor-setup__edit-input"
                  value={saveForm.name}
                  onChange={(e) => setSaveForm((f) => ({ ...f, name: e.target.value }))}
                  placeholder={t('e.g. Startup GTM Debate')}
                  maxLength={80}
                  autoFocus
                />
              </label>

              {activePresetId && (
                <label className="advisor-setup__preset-checkbox">
                  <input
                    type="checkbox"
                    checked={saveForm.updateExisting}
                    onChange={(e) => setSaveForm((f) => ({ ...f, updateExisting: e.target.checked }))}
                  />
                  <span>{t('Update existing preset')}</span>
                </label>
              )}

              <label className="advisor-setup__preset-checkbox">
                <input
                  type="checkbox"
                  checked={saveForm.isDefault}
                  onChange={(e) => setSaveForm((f) => ({ ...f, isDefault: e.target.checked }))}
                />
                <span>{t('Set as default preset')}</span>
              </label>

              <label className="advisor-setup__preset-checkbox">
                <input
                  type="checkbox"
                  checked={saveForm.includeConfig}
                  onChange={(e) => setSaveForm((f) => ({ ...f, includeConfig: e.target.checked }))}
                />
                <span>{t('Include rounds + web search settings')}</span>
              </label>
            </div>

            <div className="advisor-setup__edit-footer">
              <div className="advisor-setup__edit-footer-right">
                <button
                  type="button"
                  className="advisor-setup__edit-btn advisor-setup__edit-btn--cancel"
                  onClick={closeSavePresetModal}
                  disabled={presetSaving}
                >
                  {t('Cancel')}
                </button>
                <button
                  type="button"
                  className="advisor-setup__edit-btn advisor-setup__edit-btn--save"
                  onClick={handleSavePreset}
                  disabled={presetSaving || !saveForm.name.trim()}
                >
                  {presetSaving ? t('Saving…') : t('Save Preset')}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Edit Persona Modal */}
      {editingPersona && (
        <div className="advisor-setup__edit-overlay" onClick={closeEditModal}>
          <div className="advisor-setup__edit-modal" onClick={(e) => e.stopPropagation()}>
            <div className="advisor-setup__edit-header">
              <ReviewEmblem persona={{...editingPersona,...editForm}}/>
              <span className="advisor-setup__edit-title">{isCreatingPersona ? t('New Advisor') : t('Edit Persona')}</span>
              <button type="button" className="advisor-setup__edit-close" onClick={closeEditModal} aria-label={t('Close')}>✕</button>
            </div>

            <div className="advisor-setup__edit-body">
              <span className="advisor-setup__edit-label">评审团图标</span>
              <div className="review-icon-picker" role="group" aria-label="选择评审团图标">
                <button type="button" className="review-icon-choice" aria-pressed={editForm.avatar_emoji === 'review:auto' || (!editForm.avatar_emoji?.startsWith('review:') && !reviewIdentity({...editingPersona,...editForm}).emoji)} onClick={() => setEditForm(f => ({...f,avatar_emoji:'review:auto'}))}><ReviewEmblem persona={{...editingPersona,...editForm,avatar_emoji:'review:auto'}}/><span>按设定匹配</span></button>
                {REVIEW_IDENTITIES.map(identity => <button key={identity.id} type="button" className="review-icon-choice" aria-pressed={editForm.avatar_emoji === `review:${identity.id}`} onClick={() => setEditForm(f => ({...f,avatar_emoji:`review:${identity.id}`}))}><ReviewEmblem persona={{avatar_emoji:`review:${identity.id}`}}/><span>{identity.iconName}</span></button>)}
              </div>
              <div className="advisor-setup__edit-emoji-row">
                <label className="advisor-setup__edit-field advisor-setup__edit-field--emoji">
                  <span className="advisor-setup__edit-label">自定义表情（可选）</span>
                  <input
                    type="text"
                    className="advisor-setup__edit-input advisor-setup__edit-emoji-input"
                    value={editForm.avatar_emoji?.startsWith('review:') ? '' : editForm.avatar_emoji}
                    onChange={(e) => setEditForm((f) => ({ ...f, avatar_emoji: e.target.value }))}
                    placeholder={t('e.g. 🔍')}
                    maxLength={4}
                  />
                </label>
                <div className="advisor-setup__edit-emoji-preview">
                  <ReviewEmblem persona={{...editingPersona,...editForm}}/>
                </div>
              </div>

              <label className="advisor-setup__edit-field">
                <span className="advisor-setup__edit-label">{t('Name')}</span>
                <input
                  type="text"
                  className="advisor-setup__edit-input"
                  value={editForm.name}
                  onChange={(e) => setEditForm((f) => ({ ...f, name: e.target.value }))}
                  placeholder={isCreatingPersona ? t('e.g. The Futurist') : ''}
                />
              </label>

              <label className="advisor-setup__edit-field">
                <span className="advisor-setup__edit-label">{t('Role')}</span>
                <input
                  type="text"
                  className="advisor-setup__edit-input"
                  value={editForm.role}
                  onChange={(e) => setEditForm((f) => ({ ...f, role: e.target.value }))}
                  placeholder={isCreatingPersona ? t('e.g. Trend Forecaster') : ''}
                />
              </label>

              <label className="advisor-setup__edit-field">
                <span className="advisor-setup__edit-label">{t('Description')}</span>
                <textarea
                  className="advisor-setup__edit-textarea advisor-setup__edit-textarea--short"
                  rows={2}
                  value={editForm.description}
                  onChange={(e) => setEditForm((f) => ({ ...f, description: e.target.value }))}
                  placeholder={isCreatingPersona ? t('Shown on the advisor card in the gallery') : ''}
                />
              </label>

              <label className="advisor-setup__edit-field">
                <span className="advisor-setup__edit-label">{t('System Prompt')}</span>
                <textarea
                  className="advisor-setup__edit-textarea"
                  rows={7}
                  value={editForm.system_prompt}
                  onChange={(e) => setEditForm((f) => ({ ...f, system_prompt: e.target.value }))}
                  placeholder={isCreatingPersona ? 'You are The Futurist. Your job is to...' : ''}
                />
              </label>

              {editError && (
                <p className="advisor-setup__edit-error">{editError}</p>
              )}
            </div>

            <div className="advisor-setup__edit-footer">
              {!isCreatingPersona && editingPersona.is_customized && !editingPersona.is_custom && (
                <button
                  type="button"
                  className="advisor-setup__edit-btn advisor-setup__edit-btn--reset"
                  onClick={handleEditReset}
                  disabled={editSaving}
                >
                  {t('Reset to Default')}
                </button>
              )}
              {!isCreatingPersona && editingPersona.is_custom && (
                <button
                  type="button"
                  className="advisor-setup__edit-btn advisor-setup__edit-btn--delete"
                  onClick={handleEditDelete}
                  disabled={editSaving}
                >
                  {t('Delete Advisor')}
                </button>
              )}
              <div className="advisor-setup__edit-footer-right">
                <button
                  type="button"
                  className="advisor-setup__edit-btn advisor-setup__edit-btn--cancel"
                  onClick={closeEditModal}
                  disabled={editSaving}
                >
                  {t('Cancel')}
                </button>
                <button
                  type="button"
                  className="advisor-setup__edit-btn advisor-setup__edit-btn--save"
                  onClick={handleEditSave}
                  disabled={editSaving}
                >
                  {editSaving ? t('Saving…') : isCreatingPersona ? t('Create Advisor') : t('Save')}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
