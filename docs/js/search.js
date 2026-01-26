(function () {
    let searchIndex = null;
    const searchInput = document.getElementById('search-input');
    const searchResults = document.getElementById('search-results');

    // Debounce helper
    function debounce(func, wait) {
        let timeout;
        return function (...args) {
            clearTimeout(timeout);
            timeout = setTimeout(() => func.apply(this, args), wait);
        };
    }

    // Load Index
    fetch('search_index.json')
        .then(response => response.json())
        .then(data => {
            searchIndex = data;
            console.log("Search index loaded:", searchIndex.length, "items");
        })
        .catch(err => console.error("Failed to load search index:", err));

    // Search Logic
    function performSearch(query) {
        if (!searchIndex || !query) {
            searchResults.style.display = 'none';
            return;
        }

        query = query.toLowerCase();
        const results = searchIndex.filter(item => {
            // Simple scoring matches
            const nameMatch = item.name.toLowerCase().includes(query);
            const descMatch = item.desc && item.desc.toLowerCase().includes(query);
            return nameMatch || descMatch;
        });

        // Sort: Exact name match first, then name starts with, then description
        results.sort((a, b) => {
            const aName = a.name.toLowerCase();
            const bName = b.name.toLowerCase();

            if (aName === query) return -1;
            if (bName === query) return 1;

            if (aName.startsWith(query) && !bName.startsWith(query)) return -1;
            if (bName.startsWith(query) && !aName.startsWith(query)) return 1;

            return 0;
        });

        displayResults(results.slice(0, 50)); // Limit to 50
    }

    function displayResults(results) {
        if (results.length === 0) {
            searchResults.innerHTML = '<div class="no-results">No results found</div>';
        } else {
            searchResults.innerHTML = results.map(item => `
                <a href="${item.file}${item.anchor}" class="search-result-item">
                    <div class="result-name">${item.name}</div>
                    <div class="result-meta">${item.section} &middot; ${item.file.replace('.html', '')}</div>
                    ${item.desc ? `<div class="result-desc">${item.desc}</div>` : ''}
                </a>
            `).join('');
        }
        searchResults.style.display = 'block';
    }

    // Event Listeners
    if (searchInput) {
        searchInput.addEventListener('input', debounce(e => performSearch(e.target.value.trim()), 200));

        // Hide on click outside
        document.addEventListener('click', e => {
            if (!searchInput.contains(e.target) && !searchResults.contains(e.target)) {
                searchResults.style.display = 'none';
            }
        });

        // Show again on focus
        searchInput.addEventListener('focus', () => {
            if (searchInput.value.trim()) searchResults.style.display = 'block';
        });
    }

})();
