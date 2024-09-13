/*
KasLand Application
Copyright (c) 2024 Rymentz (rymentz.studio@gmail.com)

This work is licensed under the Creative Commons Attribution-NonCommercial 4.0 
International License. To view a copy of this license, visit:
http://creativecommons.org/licenses/by-nc/4.0/

You are free to:
- Share: copy and redistribute the material in any medium or format
- Adapt: remix, transform, and build upon the material

Under the following terms:
- Attribution: You must give appropriate credit, provide a link to the license,
  and indicate if changes were made.
- NonCommercial: You may not use the material for commercial purposes.

For any commercial use or licensing inquiries, please contact: rymentz.studio@gmail.com
*/
const container = document.getElementById('game-container');
const tilesContainer = document.getElementById('tiles-container');
const fullscreenBtn = document.getElementById('fullscreen-btn');
const infoDiv = document.getElementById('info');
const tileWidth = 100;
const tileHeight = 50;
/*To be updated for the game launch!!!*/ 
const KASPA_MAIN_ADDRESS = "kaspa:qpyps5d97q2cc5xghytl2wpxdljlk5ndglxt9f6c8hmrlev779rd544fmjhy0";
const tileCache = {};
let scale = 1;
let totalParcels;
let mapSize;
let offsetX = 0;
let offsetY = 0;
let isDragging = false;
let lastMouseX = 0;
let lastMouseY = 0;
let touchStartTime;
let touchStartX;
let touchStartY;
let isTouching = false;
let initialScale;
let gridGenerated = false;
let initialPinchDistance = 0;
let currentKaswareAccount = null;
let currentUserInfo = null;

// New structure to store data locally
let localData = {
    parcels: {},
    mapSize: 0,
    topWallets: [],
    gameInfo: {},
    lastUpdate: 0
};

// Disable global selection
document.body.style.userSelect = 'none';
document.body.style.webkitUserSelect = 'none';
document.body.style.mozUserSelect = 'none';
document.body.style.msUserSelect = 'none';

/**
 * Performs an API call.
 * @param {string} endpoint - The API endpoint.
 * @param {string} method - The HTTP method (default 'GET').
 * @param {Object} data - The data to send (optional).
 * @returns {Promise<Object>} The JSON data from the response.
 */
async function apiCall(endpoint, method = 'GET', data = null) {
    let url = `/api/${endpoint}`;
    const options = {
        method: method,
        headers: {
            'Content-Type': 'application/json',
        },
    };
    if (method === 'GET' && data) {
        const params = new URLSearchParams(data);
        url += `?${params.toString()}`;
    } else if (data) {
        options.body = JSON.stringify(data);
    }
    const response = await fetch(url, options);
    return await response.json();
}
/**
 * Initializes local data by retrieving game information from the API.
 */
async function initializeLocalData() {
    try {
        const [parcelsResponse, walletsResponse, gameInfoResponse, energyStatsResponse] = await Promise.all([
            apiCall('all_parcels'),
            apiCall('top_wallets'),
            apiCall('game_info'),
            apiCall('energy_stats')
        ]);
        
        //console.log('Nombre total de parcelles récupérées:', parcelsResponse.parcels.length);
        
        localData.mapSize = parcelsResponse.map_size;
        localData.parcels = {};
        parcelsResponse.parcels.forEach(parcel => {
            localData.parcels[`${parcel.x},${parcel.y}`] = {
                ...parcel,
            };
        });
        
        //console.log('Nombre de parcelles dans localData:', Object.keys(localData.parcels).length);
        //console.log('MapSize:', localData.mapSize);
        
        localData.topWallets = walletsResponse;
        localData.gameInfo = gameInfoResponse;
        localData.energyStats = energyStatsResponse;
        localData.previousEnergyStats = {...localData.energyStats};
        // Use the value provided by the server directly
        localData.previousPredictedZkaspaProduction = energyStatsResponse.predicted_zkaspa_production;
        localData.lastUpdate = Date.now();
        
        //console.log(`Données locales initialisées. ${Object.keys(localData.parcels).length} parcelles chargées.`);
        //console.log('Game Info:', localData.gameInfo);
        //console.log('Energy Stats:', localData.energyStats);
        
        // Update displayed information
        updateInfo();
        
        // Check KasLand status separately
        await checkKasLandStatus();
    } catch (error) {
        console.error('Erreur lors de l\'initialisation des données locales:', error);
    }
}

/**
 * Checks if the display is mobile.
 * @returns {boolean} True if the display is mobile, false otherwise.
 */
function isMobile() {
    return window.innerWidth <= 768;
}

/**
 * Periodically updates local data.
 */
async function updateLocalData() {
    console.log('Start of local data update');
    await initializeLocalData();
    console.log('Local data successfully updated');
    updateGrid(); // to update the display

}

/**
 * Checks if a parcel is in its grace period for fee payment.
 * @param {number} nextFeeDate - The date of the next fee payment.
 * @returns {boolean} True if the parcel is in grace period, false otherwise.
 */
function checkGracePeriod(nextFeeDate) {
    if (!nextFeeDate) return false;
    const now = Date.now() / 1000;
    const timeUntilFee = nextFeeDate - now;
    const gracePeriodInSeconds = 7 * 24 * 60 * 60; // 7 days in seconds
    return timeUntilFee <= gracePeriodInSeconds && timeUntilFee > 0;
}

/**
 * Updates visual energy indicators on the user interface.
 * @param {number} totalProduction - The total energy production.
 * @param {number} totalConsumption - The total energy consumption.
 * @param {number} predictedZkaspaProduction - The predicted zkaspa production.
 */
function updateEnergyIndicators(totalProduction, totalConsumption, predictedZkaspaProduction) {
    const isEnergyDeficit = totalConsumption > totalProduction;
    const indicators = document.querySelectorAll('.energy-indicator');
    
    indicators.forEach(indicator => {
        if (isEnergyDeficit) {
            indicator.classList.add('energy-deficit');
        } else {
            indicator.classList.remove('energy-deficit');
        }
    });

    // Highlight the predicted zkaspa production
    const predictedZkaspaElement = document.getElementById('predicted-zkaspa-production');
    if (predictedZkaspaElement) {
        if (isEnergyDeficit) {
            predictedZkaspaElement.textContent = '0';
            predictedZkaspaElement.classList.remove('zkaspa-production');
        } else if (predictedZkaspaProduction > 0) {
            predictedZkaspaElement.textContent = predictedZkaspaProduction.toFixed(2);
            predictedZkaspaElement.classList.add('zkaspa-production');
        } else {
            predictedZkaspaElement.textContent = '0';
            predictedZkaspaElement.classList.remove('zkaspa-production');
        }
    }

    // Update visual indicators for energy production and consumption
    const productionElement = document.getElementById('total-energy-production');
    const consumptionElement = document.getElementById('total-energy-consumption');

    if (productionElement && consumptionElement) {
        productionElement.textContent = totalProduction.toFixed(2);
        consumptionElement.textContent = totalConsumption.toFixed(2);

        if (isEnergyDeficit) {
            productionElement.classList.add('energy-deficit');
            consumptionElement.classList.add('energy-deficit');
        } else {
            productionElement.classList.remove('energy-deficit');
            consumptionElement.classList.remove('energy-deficit');
        }
    }

    // Add a visual indicator for energy deficit
    const energyStatusElement = document.getElementById('energy-status');
    if (energyStatusElement) {
        if (isEnergyDeficit) {
            energyStatusElement.textContent = 'Energy Deficit';
            energyStatusElement.classList.add('energy-deficit');
        } else {
            energyStatusElement.textContent = 'Energy Surplus';
            energyStatusElement.classList.remove('energy-deficit');
        }
    }
}

/**
 * Creates an HTML element representing a tile (parcel) on the map. Uses cache...
 */
function createTile(parcel) {
    const { x, y, building_type, building_variant, id, owner_address, is_for_sale, sale_price } = parcel;
    const key = `${x},${y}`;
    
    if (!id) {
        console.warn(`Parcel without ID ignored: x=${x}, y=${y}`);
        return null;
    }
    
    let tile = tileCache[key];
    
    if (tile) {
        // Update the existing tile
        updateTile(tile, parcel);
        return tile;
    }
    
    // Create a new tile if it doesn't exist in the cache
    tile = document.createElement('div');
    tile.className = `tile ${building_type ? building_type.toLowerCase() : 'parcel'}`;
    
    const tileImage = document.createElement('img');
    tileImage.className = 'tile-image';
    
    if (owner_address) {
        if (building_type && building_variant) {
            tileImage.src = `/static/images/${building_type.toLowerCase()}_${building_variant.toLowerCase()}.webp`;
            
            // Add the rarity indicator
            const rarityIndicator = document.createElement('div');
            rarityIndicator.className = `rarity-indicator ${parcel.rarity.toLowerCase()}`;
            rarityIndicator.textContent = parcel.rarity[0].toUpperCase(); // First letter of the rarity
            tile.appendChild(rarityIndicator);
        } else {
            console.warn(`Parcelle ${id} possédée mais sans type ou variante de bâtiment définis`);
            tileImage.src = '/static/images/parcelle.webp';
        }
    } else {
        tileImage.src = '/static/images/parcelle.webp';
    }
    
    tile.appendChild(tileImage);

    // Implémentation de KasWare
    if (owner_address && owner_address === currentKaswareAccount) {
        tile.classList.add('user-owned');
    }

    // Ajouter l'indicateur de vente si la parcelle est à vendre
    if (is_for_sale) {
        tile.classList.add('for-sale');
        const saleIndicator = document.createElement('div');
        saleIndicator.className = 'sale-indicator';
        saleIndicator.textContent = 'FOR SALE';
        tile.appendChild(saleIndicator);
    }

    const tileSpacingX = 55;
    const tileSpacingY = 27.5;
    tile.style.left = `${(x - y) * tileSpacingX}px`;
    tile.style.top = `${(x + y) * tileSpacingY}px`;
    tile.dataset.x = x;
    tile.dataset.y = y;
    
    tile.dataset.parcelId = id;
    
    // Gestionnaire d'événements pour le clic (desktop)
    tile.addEventListener('click', (event) => {
        event.stopPropagation();
        showParcelInfo(x, y);
    });

    tile.addEventListener('touchstart', (event) => {
        touchStartTime = new Date().getTime();
        touchStartX = event.touches[0].clientX;
        touchStartY = event.touches[0].clientY;
    });

    tile.addEventListener('touchend', (event) => {
        const touchEndTime = new Date().getTime();
        const touchEndX = event.changedTouches[0].clientX;
        const touchEndY = event.changedTouches[0].clientY;

        const touchDuration = touchEndTime - touchStartTime;
        const touchDistance = Math.sqrt(
            Math.pow(touchEndX - touchStartX, 2) + Math.pow(touchEndY - touchStartY, 2)
        );

        if (touchDuration < 500 && touchDistance < 10) {
            // It's a tap, not a scroll
            event.preventDefault();
            showParcelInfo(x, y);
        }
    });

    // Add the tile to the cache
    tileCache[key] = tile;

    return tile;
}

/**
 * Updates an existing tile with new information.
 * @param {HTMLElement} tile - The HTML element of the tile to update.
 * @param {Object} parcel - The new parcel data.
 */
function updateTile(tile, parcel) {
    const { building_type, building_variant, owner_address, is_for_sale, rarity } = parcel;
    
    tile.className = `tile ${building_type ? building_type.toLowerCase() : 'parcel'}`;
    
    let tileImage = tile.querySelector('.tile-image');
    if (!tileImage) {
        tileImage = document.createElement('img');
        tileImage.className = 'tile-image';
        tile.appendChild(tileImage);
    }
    
    if (owner_address) {
        if (building_type && building_variant) {
            tileImage.src = `/static/images/${building_type.toLowerCase()}_${building_variant.toLowerCase()}.webp`;
            
            // Update or add the rarity indicator
            let rarityIndicator = tile.querySelector('.rarity-indicator');
            if (!rarityIndicator) {
                rarityIndicator = document.createElement('div');
                rarityIndicator.className = 'rarity-indicator';
                tile.appendChild(rarityIndicator);
            }
            rarityIndicator.className = `rarity-indicator ${rarity.toLowerCase()}`;
            rarityIndicator.textContent = rarity[0].toUpperCase();
        } else {
            console.warn(`Parcelle possédée mais sans type ou variante de bâtiment définis`);
            tileImage.src = '/static/images/parcelle.webp';
        }
    } else {
        tileImage.src = '/static/images/parcelle.webp';
        // Remove the rarity indicator if the parcel is not owned
        const rarityIndicator = tile.querySelector('.rarity-indicator');
        if (rarityIndicator) {
            rarityIndicator.remove();
        }
    }

    // KasWare implementation
    if (parcel.owner_address && parcel.owner_address === currentKaswareAccount) {
        tile.classList.add('user-owned');
    } else {
        tile.classList.remove('user-owned');
    }

    // Handle the sale indicator
    if (is_for_sale) {
        tile.classList.add('for-sale');
        let saleIndicator = tile.querySelector('.sale-indicator');
        if (!saleIndicator) {
            saleIndicator = document.createElement('div');
            saleIndicator.className = 'sale-indicator';
            tile.appendChild(saleIndicator);
        }
        saleIndicator.textContent = 'FOR SALE';
    } else {
        tile.classList.remove('for-sale');
        const saleIndicator = tile.querySelector('.sale-indicator');
        if (saleIndicator) {
            saleIndicator.remove();
        }
    }
}

/**
 * Adds a tree border around the map. But not on mobile.
 * @param {number} mapSize - The size of the map.
 */
function addTreesBorder(mapSize) {
    const isMobileDevice = typeof isMobile === 'function' && isMobile();
    const borderWidth = isMobileDevice ? 20 : 20; // Reduce the border width on mobile
    const treeDensity = isMobileDevice ? 0.005 : 0.07; // Reduce the density on mobile

    for (let i = -borderWidth; i < mapSize + borderWidth; i++) {
        for (let j = -borderWidth; j < mapSize + borderWidth; j++) {
            if (i >= 0 && i < mapSize && j >= 0 && j < mapSize) continue; // Ignore the inside of the map

            if (Math.random() < treeDensity) {
                const tree = document.createElement('div');
                tree.className = 'tree';
                const treeImage = document.createElement('img');
                
                // Randomly choose between two types of trees
                const treeType = Math.random() < 0.5 ? 'tree1' : 'tree2';
                treeImage.src = `/static/images/${treeType}.webp`;
                
                tree.appendChild(treeImage);

                const tileSpacingX = 55;
                const tileSpacingY = 27.5;
                tree.style.left = `${(i - j) * tileSpacingX}px`;
                tree.style.top = `${(i + j) * tileSpacingY}px`;

                // Add a slight size variation for a more natural look
                const scale = isMobileDevice ? 0.6 + Math.random() * 0.3 : 0.8 + Math.random() * 0.4; // Reduce the size on mobile
                treeImage.style.transform = `scale(${scale})`;

                tilesContainer.appendChild(tree);
            }
        }
    }
}

/**
 * Displays detailed information about a parcel.
 * @param {number} x - X coordinate of the parcel.
 * @param {number} y - Y coordinate of the parcel.
 */
async function showParcelInfo(x, y) {
    const parcelKey = `${x},${y}`;
    const parcel = localData.parcels[parcelKey];
    const infoDiv = document.getElementById('parcel-info');

    if (parcel) {
        let infoMessage = '';

        if (parcel.owner_address) {
            const isInGracePeriod = checkGracePeriod(parcel.next_fee_date);
            const gracePeriodClass = isInGracePeriod ? 'grace-period' : '';
            const warningIcon = isInGracePeriod ? '⚠️ ' : '';
        
            infoMessage = `
                🆔 ID: ${parcel.id}<br>
                👤 Owner: ${parcel.owner_address}<br>
                🏠 Type: ${parcel.building_type}<br>
                🔢 Max Count: ${parcel.max_count !== null ? 
                `${parcel.current_count} / ${parcel.max_count}` : 
                'Unlimited'}<br>
                🏠 Variant: ${parcel.building_variant}<br>
                🌟 Rarity: ${parcel.rarity}<br>
                💰 Purchase amount: ${parcel.purchase_amount?.toFixed(2) || 'N/A'} KAS<br>
                📍 Coordinates: (${parcel.x}, ${parcel.y})<br>
                📅 Purchased on: ${formatTimestamp(parcel.purchase_date)}<br>
                💸 Fee amount: ${parcel.last_fee_amount} KAS<br>
                <span class="${gracePeriodClass}">
                    ${warningIcon}📅 Next fee date: ${formatTimestamp(parcel.next_fee_date)}<br>
                    ${warningIcon}⏳ Time until next fee: ${calculateTimeUntilFee(parcel.next_fee_date)}<br>
                </span>
                ⚡ Energy production: ${parcel.energy_production || 0}/day<br>
                🔋 Energy consumption: ${parcel.energy_consumption || 0}/day<br>
                💎 zkaspa production: ${parcel.zkaspa_production || 0}/day<br>
                💰 zkaspa balance: ${parcel.zkaspa_balance || 0}<br>
                📅 Last fee payment: ${formatTimestamp(parcel.last_fee_payment)}<br>
                📅 Last fee check: ${formatTimestamp(parcel.last_fee_check)}<br>
                🔄 Fee frequency: ${parcel.fee_frequency} days
            `;
            // Add sale information if the parcel is for sale
            if (parcel.is_for_sale) {
                infoMessage += `
                    <br>
                    🏷️ <strong>FOR SALE</strong><br>
                    💰 Prix de vente: ${parcel.sale_price?.toFixed(2) || 'N/A'} KAS<br>
                    👤 Adresse du vendeur: <span id="owner-address">${parcel.owner_address}</span> <button id="copy-address">Copy</button>
                `;
            }
        } else {
            infoMessage = `
                🆔 ID: ${parcel.id}<br>
                🚫 Unassigned parcel<br>
                📍 Coordinates: (${parcel.x}, ${parcel.y})<br>
            `;
        }

        infoDiv.innerHTML = infoMessage;
        infoDiv.style.display = 'block';
        infoDiv.classList.add('visible');

        // Add copy functionality only if the parcel is for sale
        if (parcel.is_for_sale) {
            const copyButton = document.getElementById('copy-address');
            if (copyButton) {
                copyButton.addEventListener('click', function() {
                    const ownerAddress = document.getElementById('owner-address').textContent;
                    navigator.clipboard.writeText(ownerAddress).then(function() {
                        alert('Address copied to clipboard!');
                    }, function(err) {
                        console.error('Could not copy text: ', err);
                    });
                });
            }
        }

        // Remove existing event listener before adding a new one
        document.removeEventListener('click', closeParcelInfo);
        document.addEventListener('click', closeParcelInfo);
    } else {
        console.error('Parcel not found in local data');
        infoDiv.innerHTML = '❌ Error: Parcel information not found.';
        infoDiv.style.display = 'block';
        infoDiv.classList.add('visible');
    }
}

/**
 * Formats a timestamp into a readable date.
 * @param {number} timestamp - The timestamp to format.
 * @returns {string} The formatted date.
 */
function formatTimestamp(timestamp) {
    if (!timestamp) return 'N/A';
    const date = new Date(timestamp * 1000);
    return date.toLocaleString('fr-FR', { timeZone: 'Europe/Paris' });
}

/**
 * Calculates the time remaining until the next fee payment.
 * @param {number} nextFeeDate - The date of the next fee payment.
 * @returns {string} The formatted remaining time.
 */
function calculateTimeUntilFee(nextFeeDate) {
    if (!nextFeeDate) return 'N/A';
    const now = Date.now() / 1000;
    const timeUntilFee = nextFeeDate - now;
    const days = Math.floor(timeUntilFee / 86400);
    const hours = Math.floor((timeUntilFee % 86400) / 3600);
    const minutes = Math.floor((timeUntilFee % 3600) / 60);
    return `${days}d ${hours}h ${minutes}m`;
}

/**
 * Closes the parcel information window.
 * @param {Event} event - The click event.
 */
function closeParcelInfo(event) {
    //console.log("closeParcelInfo called");
    const infoDiv = document.getElementById('parcel-info');
    if (event.target !== infoDiv && !infoDiv.contains(event.target)) {
        //console.log("Closing infoDiv");
        infoDiv.style.display = 'none';
        document.removeEventListener('click', closeParcelInfo);
    } else {
        //console.log("Click inside infoDiv, not closing");
    }
}

/**
 * Generates the map grid with all parcels.
 */
async function generateGrid() {
    try {
        await initializeLocalData(); // Initialiser les données locales
        
        mapSize = localData.mapSize;
        const parcels = Object.values(localData.parcels);

        // Filter valid parcels and ignore those without ID or out of bounds
        const validParcels = parcels.filter(parcel => {
            if (!parcel.id) {
                console.log("Parcelle sans ID ignorée:", parcel);
                return false;
            }
            if (parcel.x >= mapSize || parcel.y >= mapSize) {
                console.log("Out-of-bounds parcel ignored:", parcel);
                return false;
            }
            return true;
        });

        totalParcels = validParcels.length;
        updateTotalParcels();

        // Create a set to track used tile keys
        const usedTileKeys = new Set();

        validParcels.forEach(parcel => {
            const tile = createTile(parcel);
            if (tile) {
                const key = `${parcel.x},${parcel.y}`;
                usedTileKeys.add(key);
                if (!tilesContainer.contains(tile)) {
                    tilesContainer.appendChild(tile);
                }
            }
        });

        // Remove tiles that are no longer needed
        Object.keys(tileCache).forEach(key => {
            if (!usedTileKeys.has(key)) {
                const tile = tileCache[key];
                if (tilesContainer.contains(tile)) {
                    tilesContainer.removeChild(tile);
                }
                delete tileCache[key];
            }
        });

        // Add trees around the map only if it hasn't been done already
        if (!gridGenerated) {
            addTreesBorder(mapSize);
            gridGenerated = true;
        }
    } catch (error) {
        console.error('Erreur lors de la récupération des parcelles:', error);
    }
    adjustZoomForMapSize();
    
    // Move the initial view to the left
    offsetX = -mapSize * tileWidth / -2; // Adjust this value to move more or less
    
    updateMapPosition();
    updateInfo();
    gridGenerated = true;
}

/**
 * Updates the display of the total number of parcels.
 */
function updateTotalParcels() {
    const totalParcelsElement = document.getElementById('total-parcels');
    if (totalParcelsElement) {
        totalParcelsElement.textContent = totalParcels;
    }
}

/**
 * Updates the map grid.
 */
function updateGrid() {
    generateGrid();
}

/**
 * Adjusts the zoom based on the map size.
 */
function adjustZoomForMapSize() {
    const maxDimension = Math.max(container.clientWidth, container.clientHeight);
    const idealScale = maxDimension / (mapSize * Math.max(tileWidth, tileHeight));
    initialScale = Math.min(1, idealScale * 0.9);
    scale = initialScale;
    updateMapPosition();
}

/**
 * Updates the position of the map on the screen.
 */
function updateMapPosition() {
    const containerWidth = container.clientWidth;
    const containerHeight = container.clientHeight;
    
    const mapWidthPx = mapSize * tileWidth * scale;
    const mapHeightPx = mapSize * tileHeight * scale;

    // Calculate a margin that increases with zoom
    const baseMargin = containerWidth+3500 / 1; // Uses a quarter of the container width as base
    const margin = baseMargin * scale; // The margin increases when zooming

    // Calculate movement limits
    const maxOffsetX = (mapWidthPx - containerWidth) / 2 / scale + margin / scale;
    const minOffsetX = -(mapWidthPx - containerWidth) / 2 / scale - margin / scale;
    const maxOffsetY = (mapHeightPx - containerHeight) / 2 / scale + margin / scale;
    const minOffsetY = -(mapHeightPx - containerHeight) / 2 / scale - margin / scale;

    // Apply limits
    offsetX = Math.max(minOffsetX, Math.min(maxOffsetX, offsetX));
    offsetY = Math.max(minOffsetY, Math.min(maxOffsetY, offsetY));

    const translateX = containerWidth / 2 - mapWidthPx / 2 + offsetX * scale;
    const translateY = containerHeight / 2 - mapHeightPx / 2 + offsetY * scale;

    tilesContainer.style.transition = 'transform 0.2s ease-out';
    tilesContainer.style.transform = `translate(${translateX}px, ${translateY}px) scale(${scale})`;
}

/**
 * Handles map zooming.
 * @param {number} delta - The zoom direction (positive for zoom out, negative for zoom in).
 * @param {number} centerX - The X coordinate of the zoom center.
 * @param {number} centerY - The Y coordinate of the zoom center.
 */
function zoom(delta, centerX, centerY) {
    const zoomFactor = 0.1;
    const oldScale = scale;
    
    // Invert zoom direction for pinching
    const newScale = scale * (1 - delta * zoomFactor);
    
    // Allow more significant zoom in and limit zoom out to initial scale
    scale = Math.max(initialScale, Math.min(8, newScale));

    const containerRect = container.getBoundingClientRect();
    const mouseX = centerX - containerRect.left;
    const mouseY = centerY - containerRect.top;

    // Calculate cursor position relative to the map center
    const centerOffsetX = mouseX - containerRect.width / 2;
    const centerOffsetY = mouseY - containerRect.height / 2;

    // Adjust offsets to keep the zoom point centered
    offsetX += centerOffsetX / oldScale - centerOffsetX / scale;
    offsetY += centerOffsetY / oldScale - centerOffsetY / scale;

    updateMapPosition();
}

/**
 * Checks the status of KasLand (if it's full or not).
 */
async function checkKasLandStatus() {
    try {
        const status = await apiCall('kasland_status', 'GET');
        if (status.is_full) {
            // Display a message on the user interface
            const statusMessage = document.createElement('div');
            statusMessage.id = 'kasland-status';
            statusMessage.textContent = status.message;
            statusMessage.style.color = 'red';
            statusMessage.style.fontWeight = 'bold';
            document.body.prepend(statusMessage);
        } else {
            // Remove the message if it exists
            const existingMessage = document.getElementById('kasland-status');
            if (existingMessage) {
                existingMessage.remove();
            }
        }
        // Update the status in local data
        localData.kaslandStatus = status;
    } catch (error) {
        console.error('Error while checking Kasland status:', error);
    }
}

/**
 * Updates the information displayed on the user interface.
 */
function updateInfo() {
    try {
        const { gameInfo, energyStats } = localData;
        
        const updateElement = (id, value) => {
            const element = document.getElementById(id);
            if (element) {
                if (typeof value === 'number') {
                    // Use toFixed(2) only if the value has decimals
                    element.textContent = Number.isInteger(value) ? value.toString() : value.toFixed(2);
                } else {
                    element.textContent = value;
                }
            }
        };

        const updateChangePercentage = (id, currentValue, previousValue) => {
            const element = document.getElementById(id);
            if (element && typeof previousValue === 'number' && previousValue !== 0) {
                const change = ((currentValue - previousValue) / previousValue) * 100;
                const formattedChange = change.toFixed(1);
                const sign = change >= 0 ? '+' : '';
                element.textContent = ` (${sign}${formattedChange}%)`;
                element.style.color = change >= 0 ? 'green' : 'red';
            } else if (element) {
                element.textContent = '';
            }
        };

        updateElement('total-parcels', gameInfo.total_parcels);
        updateElement('community-fund', gameInfo.community_fund);
        updateElement('redistribution-amount', gameInfo.redistribution_amount);
        updateElement('unique-owners', gameInfo.unique_owners);
        updateElement('total-energy-production', energyStats.total_energy_production);
        updateElement('total-energy-consumption', energyStats.total_energy_consumption);
        updateElement('total-zkaspa', energyStats.total_zkaspa);

        // Check energy deficit for predicted zkaspa production
        const isEnergyDeficit = energyStats.total_energy_consumption > energyStats.total_energy_production;
        const predictedZkaspa = isEnergyDeficit ? 0 : energyStats.predicted_zkaspa_production;
        updateElement('predicted-zkaspa-production', predictedZkaspa);

        // Update change percentages by comparing with yesterday's statistics
        const yesterdayStats = gameInfo.yesterday_stats;

        if (yesterdayStats) {
            updateChangePercentage('energy-production-change', energyStats.total_energy_production, yesterdayStats.total_energy_production);
            updateChangePercentage('energy-consumption-change', energyStats.total_energy_consumption, yesterdayStats.total_energy_consumption);
            updateChangePercentage('zkaspa-production-change', predictedZkaspa, yesterdayStats.predicted_zkaspa_production);
        }

        updateEnergyIndicators(
            energyStats.total_energy_production,
            energyStats.total_energy_consumption,
            predictedZkaspa
        );

        // Update the energy status indicator
        const energyStatusElement = document.getElementById('energy-status');
        if (energyStatusElement) {
            energyStatusElement.textContent = isEnergyDeficit ? 'Energy Deficit' : 'Energy Surplus';
            energyStatusElement.className = isEnergyDeficit ? 'energy-deficit' : 'energy-surplus';
        }

        // Update the current event indicator
        const currentEventElement = document.getElementById('current-event');
        if (currentEventElement) {
            currentEventElement.textContent = energyStats.event_type || 'No active event';
        }

        checkKasLandStatus();
    } catch (error) {
        console.error('Erreur lors de la mise à jour des informations:', error);
    }
}

/**
 * Handles clicking on a tile.
 * @param {Event} event - The click event.
 */
function handleIsometricClick(event) {
    const rect = container.getBoundingClientRect();
    const mouseX = (event.clientX - rect.left) / scale - offsetX;
    const mouseY = (event.clientY - rect.top) / scale - offsetY;

    // Convert screen coordinates to isometric grid coordinates
    const tileX = Math.round((mouseX / tileSpacingX + mouseY / tileSpacingY) / 2);
    const tileY = Math.round((mouseY / tileSpacingY - mouseX / tileSpacingX) / 2);

    // Use these coordinates to identify the clicked parcel
    const parcelKey = `${tileX},${tileY}`;
    const parcel = localData.parcels[parcelKey];

    if (parcel) {
        showParcelInfo(tileX, tileY);
    }
}

/**
 * Handles the start of a touch on the touchscreen.
 * @param {TouchEvent} e - The touch event.
 */
function handleTouchStart(event) {
    if (event.touches.length === 2) {
        initialPinchDistance = getPinchDistance(event);
    } else {
        event.preventDefault();
        isTouching = true;
        touchStartTime = new Date().getTime();
        touchStartX = event.touches[0].clientX;
        touchStartY = event.touches[0].clientY;
        lastMouseX = touchStartX;
        lastMouseY = touchStartY;
    }
}

/**
 * Handles touch movement on the touchscreen.
 * @param {TouchEvent} e - The touch event.
 */
function handleTouchMove(event) {
    if (event.touches.length === 2) {
        const currentDistance = getPinchDistance(event);
        const delta = initialPinchDistance - currentDistance;
        // Adjust this value according to your needs
        const zoomFactor = delta * 0.01; 
        
        const centerX = (event.touches[0].clientX + event.touches[1].clientX) / 2;
        const centerY = (event.touches[0].clientY + event.touches[1].clientY) / 2;
        
        zoom(zoomFactor, centerX, centerY);
        
        initialPinchDistance = currentDistance;
    } else {
        if (!isTouching) return;
        event.preventDefault();

        const touchX = event.touches[0].clientX;
        const touchY = event.touches[0].clientY;

        const deltaX = (touchX - lastMouseX) / scale;
        const deltaY = (touchY - lastMouseY) / scale;

        offsetX += deltaX;
        offsetY += deltaY;

        lastMouseX = touchX;
        lastMouseY = touchY;

        requestAnimationFrame(updateMapPosition);
    }
}

/**
 * Handles the end of a touch on the touchscreen.
 * @param {TouchEvent} event - The touch end event.
 */
function handleTouchEnd(event) {
    event.preventDefault();
    isTouching = false;
    const touchEndTime = new Date().getTime();
    const touchEndX = event.changedTouches[0].clientX;
    const touchEndY = event.changedTouches[0].clientY;

    const touchDuration = touchEndTime - touchStartTime;
    const touchDistance = Math.sqrt(
        Math.pow(touchEndX - touchStartX, 2) + Math.pow(touchEndY - touchStartY, 2)
    );

    // Check if it's a quick tap (less than 200ms and movement less than 10px)
    if (touchDuration < 200 && touchDistance < 10) {
        // it's a quick tap
        const element = document.elementFromPoint(touchEndX, touchEndY);
        if (element && element.classList.contains('tile')) {
            // Add visual effect
            element.classList.add('tile-touched');
            
            // Remove the class after the animation
            setTimeout(() => {
                element.classList.remove('tile-touched');
            }, 300); // Corresponds to the animation duration

            const x = parseInt(element.dataset.x);
            const y = parseInt(element.dataset.y);
            showParcelInfo(x, y);
        }
    }
}

/**
 * Calculates the distance between two contact points during a pinch.
 * @param {TouchEvent} e - The touch event.
 * @returns {number} The distance between the two contact points.
 */
function getPinchDistance(event) {
    const dx = event.touches[0].clientX - event.touches[1].clientX;
    const dy = event.touches[0].clientY - event.touches[1].clientY;
    return Math.sqrt(dx * dx + dy * dy);
}

window.addEventListener('load', async () => {
    try {
        // Initialize local data
        await initializeLocalData();

        // check and init KasWare
        if (isKaswareInstalled()) {
            try {
                const accounts = await window.kasware.getAccounts();
                if (accounts.length > 0) {
                    currentKaswareAccount = accounts[0];
                }
            } catch (error) {
                console.error('Error while checking KasWare account', error);
            }
        }
        await initKasware();

        // Update the grid
        updateGrid();

        // Check maintenance status
        checkMaintenanceStatus();
        setInterval(checkMaintenanceStatus, 180000); // Check every 3 minutes

        // Check current events (if this function exists in your code)
        if (typeof checkCurrentEvents === 'function') {
            checkCurrentEvents();
        }

    } catch (error) {
        console.error('Error during application initialization:', error);
    }
});

// Update data every 3 minutes
setInterval(updateLocalData, 180000);

// Initialization
updateGrid();

// Check KasLand status every 60 seconds
setInterval(checkKasLandStatus, 60000);

// Event Listeners
window.addEventListener('resize', () => {
    adjustZoomForMapSize();
    updateMapPosition();
});

container.addEventListener('wheel', (e) => {
    e.preventDefault();
    const delta = e.deltaY > 0 ? 1 : -1;
    zoom(delta, e.clientX, e.clientY);
});

container.addEventListener('mousedown', (e) => {
    isDragging = true;
    lastMouseX = e.clientX;
    lastMouseY = e.clientY;
});

container.addEventListener('mousemove', (e) => {
    if (isDragging) {
        const deltaX = (e.clientX - lastMouseX) / scale;
        const deltaY = (e.clientY - lastMouseY) / scale;
        offsetX += deltaX;
        offsetY += deltaY;
        lastMouseX = e.clientX;
        lastMouseY = e.clientY;
        updateMapPosition();
    }
});

container.addEventListener('mouseup', () => {
    isDragging = false;
});

container.addEventListener('mouseleave', () => {
    isDragging = false;
});

fullscreenBtn.addEventListener('click', () => {
    if (!document.fullscreenElement) {
        document.documentElement.requestFullscreen();
    } else {
        if (document.exitFullscreen) {
            document.exitFullscreen();
        }
    }
});

document.addEventListener('fullscreenchange', () => {
    fullscreenBtn.textContent = document.fullscreenElement ? 'Exit Fullscreen' : 'Fullscreen';
    adjustZoomForMapSize();
    updateMapPosition();
});

document.getElementById('top-wallets-link').addEventListener('click', (e) => {
    e.preventDefault();
    try {
        const topWallets = localData.topWallets;
        
        let walletList = '<h2>Top 10 richest Kaspians (in zkaspa)</h2><ul>';
        topWallets.forEach((wallet, index) => {
            const addressStart = wallet.address.substring(0, 6);
            const addressEnd = wallet.address.substring(wallet.address.length - 4);
            walletList += `<li>${index + 1}. Address: ${addressStart}...${addressEnd} - Amount: ${wallet.amount.toFixed(2)} zkaspa</li>`;
        });
        walletList += '</ul>';
        
        const thankYouMessage = '<p>A heartfelt thank you to all our players! Your support and engagement are the driving force behind the game\'s growth and evolution. Together, we\'re shaping the future of KasLand!</p>';
        
        const topWalletsContainer = document.getElementById('top-wallets-container');
        topWalletsContainer.innerHTML = walletList + thankYouMessage + '<br><a href="#" id="back-link">Close</a>';
        topWalletsContainer.style.display = 'block';
        
        document.getElementById('back-link').addEventListener('click', (e) => {
            e.preventDefault();
            topWalletsContainer.style.display = 'none';
        });
    } catch (error) {
        console.error('Error displaying top wallets:', error);
    }
});

document.getElementById('disclaimer-link').addEventListener('click', (e) => {
    e.preventDefault();
    try {
        const disclaimerContent = `
        <h2>Disclaimer and Privacy Notice</h2>
        <p>KasLand is a game for entertainment purposes only. Virtual currencies and assets within the game have no real-world value. Players are responsible for their own actions and decisions within the game.</p>
        
        <h3>Liability</h3>
        <p>We do not guarantee continuous availability or bug-free operation of the game. Game mechanics and rules may change without prior notice. The developers and operators of KasLand are not responsible for any losses, including but not limited to:</p>
        <ul>
            <li>Bugs or glitches in the game</li>
            <li>Server downtime or closure</li>
            <li>Hacks or security breaches</li>
            <li>Loss of virtual assets or currencies</li>
            <li>Any financial losses related to the game</li>
        </ul>
        
        <h3>Data Collection and Privacy</h3>
        <p>The only data collected by KasLand are the public wallet addresses that send money to the game's address. This information is anonymous and publicly available on the Kaspa BlockDAG. We do not collect any personal information.</p>
        <p>We do not use tracking cookies on this site, and we do not sell any information to third parties.</p>
        
        <h3>GDPR Compliance</h3>
        <p>For users in the European Union: KasLand complies with the General Data Protection Regulation (GDPR). As we do not collect personal data beyond public wallet addresses, most GDPR rights (such as the right to access, rectify, or erase personal data) are not applicable in the context of this game. The automatic removal of wallet addresses due to non-payment of fees serves as a built-in data erasure mechanism.</p>
        
        <h3>Terms of Use and Privacy Policy</h3>
        <p>By playing KasLand, you agree to these terms and acknowledge that you play at your own risk. This disclaimer serves as our Terms of Use and Privacy Policy. Given the minimal data collection, we do not maintain separate, extensive documents for these policies.</p>
        
        <h3>Changes to This Notice</h3>
        <p>We reserve the right to update this disclaimer and privacy notice at any time. It is the responsibility of the users to check for updates periodically.</p>
        
        <h3>Copyright and Ownership</h3>
        <p>All assets in KasLand belong to Rymentz and are subject to copyright. Unauthorized use, reproduction, or distribution of these assets is strictly prohibited.</p>
        
        <p>If you have any questions or concerns about this disclaimer or our practices, please contact us through our Discord server.</p>
    `;
        
        const disclaimerContainer = document.getElementById('top-wallets-container'); // Reuse the same container
        disclaimerContainer.innerHTML = disclaimerContent + '<br><a href="#" id="back-link">Close</a>';
        disclaimerContainer.style.display = 'block';
        
        document.getElementById('back-link').addEventListener('click', (e) => {
            e.preventDefault();
            disclaimerContainer.style.display = 'none';
        });
    } catch (error) {
        console.error('Error displaying disclaimer:', error);
    }
});

// KASWARE WALLET IMPLEMENTATION

/**
 * Checks if the KasWare extension is installed in the browser.
 * @returns {boolean} True if KasWare is installed, false otherwise.
 */
function isKaswareInstalled() {
    return typeof window.kasware !== 'undefined';
}

/**
 * Attempts to connect to KasWare. If successful, updates the user interface and the grid.
 * @returns {Promise<string|undefined>} The connected account address or undefined if failed.
 */
async function connectKasware() {
    if (!isKaswareInstalled()) {
        alert('The KasWare extension is not installed in your browser. Please install it to continue.');
        return;
    }
    
    try {
        if (currentKaswareAccount) {
            // If already connected, do nothing
            //console.log('Already connected to KasWare');
            return currentKaswareAccount;
        } else {
            // If not connected, request connection
            const accounts = await window.kasware.requestAccounts();
            currentKaswareAccount = accounts[0];
            await updateKaswareBar();
            updateGrid();
            return currentKaswareAccount;
        }
    } catch (error) {
        console.error('Failed to connect to KasWare', error);
        alert('Failed to connect to KasWare. Please try again.');
    }
}

/**
 * Updates the KasWare bar user interface based on the connection status. Displays user information.
 */
async function updateKaswareBar() {
    const connectButton = document.getElementById('connect-kasware');
    const addressSpan = document.getElementById('kasware-address');
    const infoDiv = document.getElementById('kasware-info');
    
    if (currentKaswareAccount) {
        const addressStart = currentKaswareAccount.slice(0, 6);
        const addressEnd = currentKaswareAccount.slice(-4);
        addressSpan.textContent = `${addressStart}...${addressEnd}`;
        connectButton.classList.add('connected');
        
        // Display user information
        await updateUserInfo();
    } else {
        addressSpan.textContent = 'Connect to KasWare';
        infoDiv.style.display = 'none';
        connectButton.classList.remove('connected');
    }
}

/**
 * Sets up event listeners for account changes.
 */
function setupKaswareEvents() {
    if (!isKaswareInstalled()) return;

    window.kasware.on('accountsChanged', (accounts) => {
        console.log('KasWare accounts changed', accounts);
        currentKaswareAccount = accounts[0] || null;
        updateKaswareBar();
    });

}

/**
 * Initializes KasWare by updating the bar, setting up events, and adding a click listener to the connect button.
 */
async function initKasware() {
    //console.log("Initializing KasWare");
    setupKaswareEvents();
    
    const connectButton = document.getElementById('connect-kasware');
    if (connectButton) {
        //console.log("Connection button found, adding event listener");
        connectButton.addEventListener('click', connectKasware);
    } else {
        console.error("Connection button not found");
    }

    if (isKaswareInstalled()) {
        try {
            const accounts = await window.kasware.getAccounts();
            if (accounts.length > 0) {
                currentKaswareAccount = accounts[0];
                await updateKaswareBar();
                await updateUserInfo();  // Add this line
                updateGrid();  // Add this line if necessary
            }
        } catch (error) {
            console.error('Error while checking KasWare account', error);
        }
    }
}

/**
 * Retrieves and displays user information (zkaspa balance and parcel ID) from the API.
 */
async function updateUserInfo() {
    const infoDiv = document.getElementById('kasware-info');
    const addressSpan = document.getElementById('kasware-address');
    
    if (currentKaswareAccount) {
        try {
            // Iterate through all parcels in the local cache
            const userParcel = Object.values(localData.parcels).find(parcel => parcel.owner_address === currentKaswareAccount);
            
            let infoText = '';
            let zkaspaBalance = 0;
            
            if (userParcel) {
                infoText = `Parcel ID: ${userParcel.id} | `;
                zkaspaBalance = userParcel.zkaspa_balance || 0;
            } else {
                infoText = `No parcel | `;
            }
            
            infoText += `${zkaspaBalance.toFixed(2)} zkaspa`;
            
            infoDiv.textContent = infoText;
            infoDiv.style.display = 'inline';
            
            const addressStart = currentKaswareAccount.slice(0, 6);
            const addressEnd = currentKaswareAccount.slice(-4);
            addressSpan.textContent = `${addressStart}...${addressEnd}`;
        } catch (error) {
            console.error('Error while retrieving user information:', error);
            infoDiv.textContent = `Error: ${error.message}`;
            infoDiv.style.display = 'inline';
        }
    } else {
        infoDiv.style.display = 'none';
        addressSpan.textContent = 'Connect to KasWare';
    }
}

document.addEventListener('DOMContentLoaded', function() {
    const legend = document.getElementById('legend');
    const legendHeader = document.getElementById('legend-header');
    const closeLegendBtn = document.getElementById('close-legend');
    const showLegendBtn = document.getElementById('show-legend');
    const shopInfoBtn = document.getElementById('shop-info');
    shopInfoBtn.addEventListener('click', toggleShopInfo);
    const infoDiv = document.getElementById('info');
    const closeInfoBtn = document.getElementById('close-info');
    const toggleInfoBtn = document.getElementById('toggle-info');

    closeInfoBtn.addEventListener('click', function() {
        infoDiv.style.display = 'none';
        if (isMobile()) {
            toggleInfoBtn.style.display = 'flex'; // Use 'flex' instead of 'block' for mobile controls
        } else {
            toggleInfoBtn.style.display = 'block';
        }
    });

    toggleInfoBtn.addEventListener('click', function() {
        infoDiv.style.display = 'block';
        toggleInfoBtn.style.display = 'none';
    });

    /**
     * Toggles the display of shop information.
     */
    function toggleShopInfo() {
        const shopInfoContainer = document.getElementById('shop-info-container');
        if (shopInfoContainer.style.display === 'none' || shopInfoContainer.style.display === '') {
            showShopInfo();
        } else {
            hideShopInfo();
        }
    }

    /**
     * Displays information about the KasLand main wallet.
     */
    function showShopInfo() {
        const shopInfoContainer = document.getElementById('shop-info-container');
        shopInfoContainer.innerHTML = `
    <h2>KasLand Buy / Sell Parcel Information</h2>

    <h3>Critical Wallet Information</h3>
    <p>To participate in KasLand transactions, it's crucial to use a wallet that maintains a consistent address across multiple transactions. We strongly recommend using:</p>
    <ul>
        <li>https://www.kasware.xyz</li>
        <li>Any other wallet that doesn't change your address after transactions</li>
    </ul>
    <div class="warning-box">
        <h4>⚠️ Important Warning ⚠️</h4>
        <p>Using a wallet that changes address after transactions may result in loss of funds or parcels. These losses cannot and will not be refunded or recovered.</p>
        <p>KasLand is not responsible for any losses incurred due to the use of incompatible wallets. Always ensure you're using a wallet with a consistent address before engaging in any transactions.</p>
    </div>

    <h3>Buying a New Parcel</h3>
    <p>To buy a new parcel and add a building in KasLand, simply send KAS to the following address:</p>
    <div class="address-container">
        <input type="text" id="kaspa-address" value="${KASPA_MAIN_ADDRESS}" readonly>
        <button id="copy-address">Copy</button>
    </div>
    <p>The amount you send determines the type of building you'll get. Check the Legend for tier information.</p>

    <h3>Selling Your Parcel</h3>
    <p>To put your parcel up for sale:</p>
    <ol>
        <li>Send exactly 0.2 KAS to the KasLand address above.</li>
        <li>Your parcel will be listed for sale at the total amount you've invested in it.</li>
    </ol>

    <h3>Cancelling a Sale</h3>
    <p>To cancel the sale of your parcel:</p>
    <ol>
        <li>Send exactly 0.3 KAS to the KasLand address above.</li>
        <li>Your parcel will be removed from the sale listing.</li>
    </ol>

    <h3>Buying an Existing Parcel</h3>
    <p>To buy a parcel that's for sale:</p>
    <ol>
        <li>Find a parcel marked "FOR SALE" on the map.</li>
        <li>Click on it to see the sale price.</li>
        <li><strong>Send the exact sale price amount to the wallet address of the parcel's current owner.</strong></li>
        <li>The parcel ownership will be transferred to you automatically.</li>
    </ol>
    <p><strong>Important Notes:</strong></p>
    <ul>
        <li>Each player can own only one plot at a time.</li>
        <li>Buying a new plot will result in losing ownership of your current plot.</li>
        <li>Your zKaspa balance is transferred when buying a new plot, but all other building attributes from your old plot are reset.</li>
    </ul>

    <p>Note: Transactions may take a few minutes to process. Refresh the page if you don't see changes immediately.</p>

    <p>If you're a business interested in having a special building in KasLand, or if you're just interested 
    in getting involved in the democratic life of KasLand, please join us on our Discord server.</p>
    <button id="close-shop-info">Close</button>
    `;
        shopInfoContainer.style.display = 'block';
        
        document.getElementById('close-shop-info').addEventListener('click', hideShopInfo);
        document.getElementById('copy-address').addEventListener('click', copyAddress);
    }

    /**
     * Copies the Kaspa address to the clipboard.
     */
    function copyAddress() {
        const addressInput = document.getElementById('kaspa-address');
        addressInput.select();
        document.execCommand('copy');
        
        // Optional: Display a confirmation message
        const copyButton = document.getElementById('copy-address');
        const originalText = copyButton.textContent;
        copyButton.textContent = 'Copié !';
        setTimeout(() => {
            copyButton.textContent = originalText;
        }, 2000);
    }

    /**
     * Hides the KasLand shop information.
     */  
    function hideShopInfo() {
        const shopInfoContainer = document.getElementById('shop-info-container');
        shopInfoContainer.style.display = 'none';
    }

    /**
     * Toggles the legend display (expansion for mobile, show/hide for desktop).
     */
    function toggleLegend() {
        if (isMobile()) {
            legend.classList.toggle('expanded');
        } else {
            legend.style.display = legend.style.display === 'none' || legend.style.display === '' ? 'block' : 'none';
        }
        updateLegendButtonText();
    }

    /**
     * Updates the text of the legend display button.
     */
    function updateLegendButtonText() {
        if (isMobile()) {
            showLegendBtn.textContent = legend.classList.contains('expanded') ? 'Hide Legend' : 'Show Legend';
        } else {
            showLegendBtn.textContent = legend.style.display === 'none' || legend.style.display === '' ? 'Show Legend' : 'Hide Legend';
        }
    }

    /**
     * Updates the legend display based on the device type.
     */
    function updateLegendDisplay() {
        if (isMobile()) {
            legend.style.display = 'block';
            legend.classList.remove('expanded');
        } else {
            legend.style.display = 'none';
        }
        updateLegendButtonText();
    }

    // Handle click on the legend header (for mobile)
    legendHeader.addEventListener('click', function(e) {
        if (isMobile()) {
            toggleLegend();
            e.stopPropagation();
        }
    });

    // Handle click on the close button (for desktop)
    if (closeLegendBtn) {
        closeLegendBtn.addEventListener('click', toggleLegend);
    }

    // Handle click on the Show/Hide Legend button
    showLegendBtn.addEventListener('click', toggleLegend);

    // Initial configuration
    updateLegendDisplay();

    // For KasWare wallet integration, we call initKasware
    if (isKaswareInstalled()) {
        try {
            window.kasware.getAccounts().then(accounts => {
                if (accounts.length > 0) {
                    currentKaswareAccount = accounts[0];
                }
                initKasware();
            });
        } catch (error) {
            console.error('Error while checking KasWare account', error);
            initKasware();
        }
    } else {
        initKasware();
    }

    // Adjust the legend display when resizing the window
    window.addEventListener('resize', updateLegendDisplay);
});

container.addEventListener('touchstart', handleTouchStart, { passive: false });
container.addEventListener('touchmove', handleTouchMove, { passive: false });
container.addEventListener('touchend', handleTouchEnd, { passive: false });
container.addEventListener('touchcancel', handleTouchEnd, { passive: false });

// Prevent image dragging
container.addEventListener('dragstart', (e) => {
    e.preventDefault();
});

/**
 * Checks the game's maintenance status.
 */
function checkMaintenanceStatus() {
    fetch('/static/maintenance.json')
        .then(response => response.text())
        .then(text => {
            try {
                const data = JSON.parse(text);
                if (data.maintenanceMode) {
                    showMaintenanceMessage(data.message);
                } else {
                    hideMaintenanceMessage();
                }
            } catch (error) {
                console.error('Erreur de parsing JSON:', error);
                console.log('Contenu du fichier:', text);
            }
        })
        .catch(error => console.error('Error while checking maintenance status:', error));
}

/**
 * Displays a maintenance message on the user interface.
 * @param {string} message - The maintenance message to display.
 */
function showMaintenanceMessage(message) {
    let maintenanceDiv = document.getElementById('maintenance-message');
    if (!maintenanceDiv) {
        maintenanceDiv = document.createElement('div');
        maintenanceDiv.id = 'maintenance-message';
        document.body.prepend(maintenanceDiv);
    }
    maintenanceDiv.textContent = message;
    maintenanceDiv.style.display = 'block';
    document.body.classList.add('has-maintenance-message');
}

/**
 * Hides the maintenance message.
 */
function hideMaintenanceMessage() {
    const maintenanceDiv = document.getElementById('maintenance-message');
    if (maintenanceDiv) {
        maintenanceDiv.remove();
    }
}

/**
 * Checks current events in the game.
 */
function checkCurrentEvents() {
    fetch('/api/current_events')
        .then(response => response.json())
        .then(events => {
            const indicator = document.getElementById('current-event-indicator');
            const eventName = document.getElementById('current-event-name');

            if (events.length > 0) {
                const event = events[0]; // Take the first event if there are multiple
                eventName.textContent = event.type;
                indicator.style.display = 'flex';
                showEventPopup(event);
            } else {
                indicator.style.display = 'none';
            }
        })
        .catch(error => console.error('Erreur lors de la vérification des événements:', error));
}

let currentEventId = null;

/**
 * Displays a popup window for a new event.
 * @param {Object} event - The event data.
 */
function showEventPopup(event) {
    if (event.id === currentEventId) {
        return; // Don't display the popup if the event is already displayed
    }

    currentEventId = event.id;
    const popupContainer = document.createElement('div');
    popupContainer.className = 'event-popup';
    popupContainer.innerHTML = `
        <h3>New event</h3>
        <p>${event.description}</p>
        <p>Event end: ${new Date(event.end_time * 1000).toLocaleString()}</p>
        <button onclick="this.parentElement.remove()">Close</button>
    `;
    document.body.appendChild(popupContainer);

    // Position the popup under the KasWare bar
    const kaswareBarHeight = 60; // Adjust this value if necessary
    const topPosition = Math.max(kaswareBarHeight + 20, window.scrollY + kaswareBarHeight + 20);
    popupContainer.style.top = `${topPosition}px`;

    // Adjust the popup position when scrolling
    function adjustPopupPosition() {
        const newTopPosition = Math.max(kaswareBarHeight + 20, window.scrollY + kaswareBarHeight + 20);
        popupContainer.style.top = `${newTopPosition}px`;
    }

    window.addEventListener('scroll', adjustPopupPosition);

    // Clean up the event listener when the popup is closed
    popupContainer.querySelector('button').addEventListener('click', function() {
        window.removeEventListener('scroll', adjustPopupPosition);
    });
}

// Check events every 5 minutes
setInterval(checkCurrentEvents, 5 * 60 * 1000);

// Check events on page load
document.addEventListener('DOMContentLoaded', checkCurrentEvents);