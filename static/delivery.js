
class DeliveryCalculator {
    constructor() {
        this.deliveryForm = document.getElementById('delivery-form');
        this.addressInput = document.getElementById('customer-address');
        this.calculateBtn = document.getElementById('calculate-delivery');
        this.resultDiv = document.getElementById('delivery-result');
        
        this.initEventListeners();
        this.loadDeliveryZones();
    }
    
    initEventListeners() {
        if (this.calculateBtn) {
            this.calculateBtn.addEventListener('click', () => this.calculateDelivery());
        }
        
        if (this.addressInput) {
            this.addressInput.addEventListener('keypress', (e) => {
                if (e.key === 'Enter') {
                    this.calculateDelivery();
                }
            });
        }
    }
    
    async calculateDelivery() {
        const address = this.addressInput?.value?.trim();
        
        if (!address) {
            this.showError('Please enter a delivery address');
            return;
        }
        
        this.showLoading();
        
        try {
            const response = await fetch('/calculate-delivery', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ address: address })
            });
            
            const data = await response.json();
            
            if (data.success) {
                this.showResult(data);
            } else {
                this.showError(data.error || 'Failed to calculate delivery charge');
            }
        } catch (error) {
            this.showError('Network error. Please try again.');
            console.error('Delivery calculation error:', error);
        }
    }
    
    showResult(data) {
        if (this.resultDiv) {
            this.resultDiv.innerHTML = `
                <div class="delivery-result success">
                    <h3>Delivery Information</h3>
                    <p><strong>Distance:</strong> ${data.distance_km} km</p>
                    <p><strong>Delivery Charge:</strong> $${data.delivery_charge}</p>
                    <p><strong>Estimated Delivery Time:</strong> ${this.getEstimatedTime(data.distance_km)}</p>
                </div>
            `;
        }
    }
    
    showError(message) {
        if (this.resultDiv) {
            this.resultDiv.innerHTML = `
                <div class="delivery-result error">
                    <p>Error: ${message}</p>
                </div>
            `;
        }
    }
    
    showLoading() {
        if (this.resultDiv) {
            this.resultDiv.innerHTML = `
                <div class="delivery-result loading">
                    <p>Calculating delivery charge...</p>
                </div>
            `;
        }
    }
    
    getEstimatedTime(distance) {
        if (distance <= 5) return '30-45 minutes';
        if (distance <= 10) return '45-60 minutes';
        if (distance <= 20) return '1-1.5 hours';
        if (distance <= 50) return '1.5-2.5 hours';
        return '2.5-4 hours';
    }
    
    async loadDeliveryZones() {
        try {
            const response = await fetch('/delivery-zones');
            const data = await response.json();
            this.displayDeliveryZones(data.delivery_zones);
        } catch (error) {
            console.error('Failed to load delivery zones:', error);
        }
    }
    
    displayDeliveryZones(zones) {
        const zonesDiv = document.getElementById('delivery-zones');
        if (zonesDiv && zones) {
            zonesDiv.innerHTML = `
                <h3>Delivery Zones & Pricing</h3>
                <div class="zones-grid">
                    ${zones.map(zone => `
                        <div class="zone-card">
                            <h4>${zone.range}</h4>
                            <p class="price">$${zone.charge}</p>
                            <p class="description">${zone.description}</p>
                        </div>
                    `).join('')}
                </div>
            `;
        }
    }
}

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    new DeliveryCalculator();
});
