package com.ecommerce.user.dto;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * Pins the corrected JSON field naming for {@link AddressResponse#isDefault},
 * mirroring {@link AddressRequestJsonTest}: responses returned to black-box
 * clients must expose the boolean under the literal key "isDefault".
 */
class AddressResponseJsonTest {

    @Test
    void isDefault_serializesToJsonKeyIsDefault() throws Exception {
        ObjectMapper mapper = new ObjectMapper();
        AddressResponse response = new AddressResponse();
        response.setDefault(true);

        String json = mapper.writeValueAsString(response);

        assertTrue(json.contains("\"isDefault\":true"));
    }

    @Test
    void isDefault_deserializesFromJsonKeyIsDefault() throws Exception {
        ObjectMapper mapper = new ObjectMapper();
        String json = "{\"addressId\":1,\"province\":\"Guangdong\",\"city\":\"Shenzhen\","
                + "\"district\":\"Nanshan\",\"detail\":\"No.1\",\"isDefault\":true}";

        AddressResponse response = mapper.readValue(json, AddressResponse.class);

        assertTrue(response.isDefault());
    }
}
