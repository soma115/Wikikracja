window.wkOnReady(function() {
	const resourceSection = document.querySelector('[data-resource-section]');
	if (!resourceSection) return;

	const resourceName = resourceSection.querySelector('[data-resource-name]');
	const resourceKind = resourceSection.querySelector('[name="kind"]');
	const entityType = resourceSection.querySelector('[name="entity_type"]');
	const resourceSuggestions = resourceSection.querySelector('[data-resource-suggestions]');
	let searchTimer;

	const resourceKindRequired = resourceSection.dataset.resourceKindRequired !== 'false';
	const supportsResourceSuggestions = () => !entityType || ['all', 'resource'].includes(entityType.value);

	function hideResourceSuggestions() {
		resourceSuggestions.replaceChildren();
		resourceSuggestions.classList.remove('tw-show');
	}

	function updateResourceSearchState() {
		resourceName.disabled = resourceKindRequired && !resourceKind.value;
		if ((resourceKindRequired && !resourceKind.value) || !supportsResourceSuggestions()) {
			hideResourceSuggestions();
		}
	}

	resourceKind.addEventListener('change', updateResourceSearchState);
	entityType?.addEventListener('change', updateResourceSearchState);
	resourceName.addEventListener('input', function() {
		if (!supportsResourceSuggestions()) return;
		if (resourceKindRequired && !resourceKind.value) return;
		clearTimeout(searchTimer);
		searchTimer = setTimeout(() => {
			const params = new URLSearchParams({q: resourceName.value});
			if (resourceKind.value) params.set('kind', resourceKind.value);
			if (entityType) params.set('entity_type', entityType.value);
			fetch(`${resourceSection.dataset.resourceSearchUrl}?${params}`)
				.then(response => response.json())
				.then(data => {
					if (!supportsResourceSuggestions()) return;
					resourceSuggestions.replaceChildren(...data.items.map(item => {
						const option = document.createElement('button');
						option.type = 'button';
						option.className = 'tw-dropdown-item tw-block tw-w-full tw-text-start';
						option.textContent = item.name;
						option.addEventListener('click', function() {
							resourceName.value = item.name;
							hideResourceSuggestions();
						});
						return option;
					}));
					resourceSuggestions.classList.toggle('tw-show', data.items.length > 0);
				})
				.catch(hideResourceSuggestions);
		}, 250);
	});

	updateResourceSearchState();
});
