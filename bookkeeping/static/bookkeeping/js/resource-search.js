window.wkOnReady(function() {
	const resourceSection = document.querySelector('[data-resource-section]');
	if (!resourceSection) return;

	const resourceName = resourceSection.querySelector('[data-resource-name]');
	const resourceKind = resourceSection.querySelector('[name="kind"]');
	const resourceSuggestions = resourceSection.querySelector('[data-resource-suggestions]');
	let searchTimer;

	const resourceKindRequired = resourceSection.dataset.resourceKindRequired !== 'false';

	function hideResourceSuggestions() {
		resourceSuggestions.replaceChildren();
		resourceSuggestions.classList.remove('tw-show');
	}

	function updateResourceSearchState() {
		resourceName.disabled = resourceKindRequired && !resourceKind.value;
		if (resourceKindRequired && !resourceKind.value) {
			hideResourceSuggestions();
		}
	}

	resourceKind.addEventListener('change', updateResourceSearchState);
	resourceName.addEventListener('input', function() {
		if (resourceKindRequired && !resourceKind.value) return;
		clearTimeout(searchTimer);
		searchTimer = setTimeout(() => {
			const params = new URLSearchParams({q: resourceName.value});
			if (resourceKind.value) params.set('kind', resourceKind.value);
			fetch(`${resourceSection.dataset.resourceSearchUrl}?${params}`)
				.then(response => response.json())
				.then(data => {
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
