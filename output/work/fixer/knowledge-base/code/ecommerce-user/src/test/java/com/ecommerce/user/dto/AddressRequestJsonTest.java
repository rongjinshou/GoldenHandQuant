package com.ecommerce.user.dto;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * Pins the corrected JSON field naming for {@link AddressRequest#isDefault}
 * (design-implementation fix: the black-box fixture posts the literal key
 * "isDefault", but a bare {@code isDefault()}/{@code setDefault()} pair
 * would have Jackson infer the property name "default" instead).
 */
class AddressRequestJsonTest {

    @Test
    void isDefault_deserializesFromJsonKeyIsDefault() throws Exception {
        ObjectMapper mapper = new ObjectMapper();
        String json = "{\"province\":\"Guangdong\",\"city\":\"Shenzhen\","
                + "\"district\":\"Nanshan\",\"detail\":\"No.1\",\"isDefault\":true}";

        AddressRequest request = mapper.readValue(json, AddressRequest.class);

        assertTrue(request.isDefault());
    }

    @Test
    void isDefault_serializesToJsonKeyIsDefault() throws Exception {
        ObjectMapper mapper = new ObjectMapper();
        AddressRequest request = new AddressRequest();
        request.setDefault(true);

        String json = mapper.writeValueAsString(request);

        assertTrue(json.contains("\"isDefault\":true"));
    }

    @Test
    void isDefault_doesNotSerializeAsBareDefault() throws Exception {
        ObjectMapper mapper = new ObjectMapper();
        AddressRequest request = new AddressRequest();
        request.setDefault(true);

        String json = mapper.writeValueAsString(request);

        assertEquals(false, json.contains("\"default\":true"));
    }
}
