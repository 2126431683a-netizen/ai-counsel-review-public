import { useMemo } from 'react';
import Select from 'react-select';
import { useI18n } from '../i18n';

/**
 * Searchable model selector using react-select.
 * Provides type-to-filter functionality for large model lists.
 */
export default function SearchableModelSelect({
  models,
  value,
  onChange,
  placeholder = "Search and select a model...",
  isDisabled = false,
  isLoading = false,
  allModels = null, // Optional: all models to find current value if filtered out
  autoOpen = false,
  appearance = 'dark',
}) {
  const { t } = useI18n();
  const paper = appearance === 'paper';

  // Convert models to react-select format with grouping
  const groupedOptions = models.reduce((acc, model) => {
    // Determine group label
    let groupLabel;
    // Use source field if available, otherwise fallback to provider check
    const isOpenRouter = model.source === 'openrouter' || model.provider === 'OpenRouter';
    const isOllama = model.id?.startsWith('ollama:') || model.provider === 'Ollama';
    const isXaiOAuth = model.id?.startsWith('xai-oauth:') || model.source === 'xai-oauth';
    const isOpenAiOAuth = model.id?.startsWith('openai-oauth:') || model.source === 'openai-oauth';
    const isCopilot = model.id?.startsWith('github-copilot:') || model.source === 'github-copilot';

    if (isOpenRouter) {
      groupLabel = 'OpenRouter (Cloud)';
    } else if (isOllama) {
      groupLabel = 'Local (Ollama)';
    } else if (isXaiOAuth) {
      groupLabel = 'xAI SuperGrok (Subscription)';
    } else if (isOpenAiOAuth) {
      groupLabel = 'ChatGPT Plus/Pro (Subscription)';
    } else if (isCopilot) {
      groupLabel = 'GitHub Copilot (Subscription)';
    } else {
      groupLabel = `${model.provider || 'Direct'} (Direct)`;
    }

    if (!acc[groupLabel]) {
      acc[groupLabel] = [];
    }
    acc[groupLabel].push({
      value: model.id,
      label: model.name,
      model: model, // Keep full model data for reference
    });
    return acc;
  }, {});

  // Convert to react-select grouped format
  const providerOrder = [
    'OpenAI (Direct)', 'Anthropic (Direct)', 'Google (Direct)', 'Mistral (Direct)', 'DeepSeek (Direct)',
    'Groq (Direct)',
    'xAI SuperGrok (Subscription)', 'ChatGPT Plus/Pro (Subscription)', 'GitHub Copilot (Subscription)',
    'OpenRouter (Cloud)',
    'Local (Ollama)'
  ];

  const options = Object.keys(groupedOptions)
    .sort((a, b) => {
      const indexA = providerOrder.indexOf(a);
      const indexB = providerOrder.indexOf(b);
      if (indexA !== -1 && indexB !== -1) return indexA - indexB;
      if (indexA !== -1) return -1;
      if (indexB !== -1) return 1;
      return a.localeCompare(b);
    })
    .map(group => ({
      label: group
        .replace(' (Cloud)', ` (${t('Cloud')})`)
        .replace(' (Subscription)', ` (${t('Subscription')})`)
        .replace(' (Direct)', ` (${t('Direct')})`)
        .replace(/^Local/, t('Local')),
      options: groupedOptions[group],
    }));

  // Find current value in options
  let selectedOption = options
    .flatMap(group => group.options)
    .find(opt => opt.value === value) || null;

  // If current value not found in filtered options, try to find it in allModels
  // This keeps the selection visible even when filtered out
  if (!selectedOption && value && allModels) {
    const currentModel = allModels.find(m => m.id === value);
    if (currentModel) {
      selectedOption = {
        value: currentModel.id,
        label: `${currentModel.name} (${t('filtered')})`,
        model: currentModel,
      };
    }
  }

  const customStyles = useMemo(() => ({
    control: (base, state) => ({
      ...base,
      backgroundColor: paper ? '#faf8ee' : 'rgba(30, 41, 59, 0.8)',
      borderColor: state.isFocused ? '#185bac' : paper ? '#10110f' : 'rgba(148, 163, 184, 0.2)',
      borderRadius: paper ? '4px' : '8px',
      borderWidth: 1,
      minHeight: '38px',
      boxShadow: state.isFocused ? paper ? '0 0 0 2px #185bac' : '0 0 0 2px rgba(59, 130, 246, 0.3)' : 'none',
      transition: 'box-shadow 300ms ease-in-out',
      '&:hover': {
        borderColor: '#3b82f6',
      },
    }),
    menu: (base) => ({
      ...base,
      backgroundColor: paper ? '#fffef9' : 'rgba(30, 41, 59, 0.98)',
      borderRadius: paper ? '4px' : '8px',
      border: paper ? '2px solid #10110f' : '1px solid rgba(148, 163, 184, 0.2)',
      boxShadow: paper ? '4px 4px 0 #10110f' : '0 10px 40px rgba(0, 0, 0, 0.5)',
      zIndex: 100,
      minWidth: 'min(360px, calc(100vw - 32px))',
      maxWidth: 'calc(100vw - 32px)',
    }),
    menuPortal: (base) => ({
      ...base,
      zIndex: 9999,
    }),
    menuList: (base) => ({
      ...base,
      maxHeight: '300px',
      padding: '4px',
    }),
    group: (base) => ({
      ...base,
      paddingTop: '8px',
      paddingBottom: '4px',
    }),
    groupHeading: (base) => ({
      ...base,
      color: paper ? '#596575' : '#94a3b8',
      fontSize: 'calc(11px * var(--font-scale))',
      fontWeight: '600',
      textTransform: paper ? 'none' : 'uppercase',
      letterSpacing: '0.5px',
      marginBottom: '4px',
      paddingLeft: '8px',
    }),
    option: (base, state) => ({
      ...base,
      backgroundColor: paper ? state.isSelected ? '#10110f' : state.isFocused ? '#fff0a4' : '#fffef9' : state.isSelected
        ? 'rgba(59, 130, 246, 0.3)'
        : state.isFocused
          ? 'rgba(59, 130, 246, 0.15)'
          : 'transparent',
      color: paper ? state.isSelected ? '#faf8ee' : '#10110f' : state.isSelected ? '#ffffff' : '#e2e8f0',
      boxShadow: 'none',
      padding: '8px 12px',
      borderRadius: paper ? '2px' : '4px',
      cursor: 'pointer',
      fontSize: 'calc(13px * var(--font-scale))',
      '&:active': {
        backgroundColor: paper ? '#ffd21c' : 'rgba(59, 130, 246, 0.4)',
      },
    }),
    singleValue: (base) => ({
      ...base,
      color: paper ? '#10110f' : '#e2e8f0',
      fontSize: 'calc(13px * var(--font-scale))',
    }),
    input: (base) => ({
      ...base,
      color: paper ? '#10110f' : '#e2e8f0',
    }),
    placeholder: (base) => ({
      ...base,
      color: '#64748b',
      fontSize: 'calc(13px * var(--font-scale))',
    }),
    indicatorSeparator: () => ({
      display: 'none',
    }),
    dropdownIndicator: (base) => ({
      ...base,
      color: '#64748b',
      padding: '6px',
      '&:hover': {
        color: '#94a3b8',
      },
    }),
    clearIndicator: (base) => ({
      ...base,
      color: '#64748b',
      padding: '6px',
      '&:hover': {
        color: '#f87171',
      },
    }),
    noOptionsMessage: (base) => ({
      ...base,
      color: '#64748b',
      fontSize: 'calc(13px * var(--font-scale))',
    }),
    loadingMessage: (base) => ({
      ...base,
      color: '#64748b',
    }),
  }), [paper]);

  return (
    <Select
      options={options}
      value={selectedOption}
      onChange={(option) => onChange(option ? option.value : '')}
      placeholder={t(placeholder)}
      aria-label={t('Search and select a model...')}
      isDisabled={isDisabled}
      isLoading={isLoading}
      isClearable
      isSearchable
      autoFocus={autoOpen}
      defaultMenuIsOpen={autoOpen}
      styles={customStyles}
      menuPortalTarget={document.body}
      classNamePrefix="model-select"
      noOptionsMessage={() => t('No models found')}
      loadingMessage={() => t('Loading models...')}
      filterOption={(option, inputValue) => {
        if (!inputValue) return true;
        // Normalize dashes/underscores to spaces so "kimi k2" matches "kimi-k2"
        const normalize = (s) => s.toLowerCase().replace(/[-_]/g, ' ');
        const q = normalize(inputValue);
        return normalize(option.label).includes(q) || normalize(option.value).includes(q);
      }}
    />
  );
}
