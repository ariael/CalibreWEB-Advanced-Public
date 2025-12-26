/* This file is part of the Calibre-Web (https://github.com/janeczku/calibre-web)
 *    Copyright (C) 2018 OzzieIsaacs
 *
 *  This program is free software: you can redistribute it and/or modify
 *  it under the terms of the GNU General Public License as published by
 *  the Free Software Foundation, either version 3 of the License, or
 *  (at your option) any later version.
 *
 *  This program is distributed in the hope that it will be useful,
 *  but WITHOUT ANY WARRANTY; without even the implied warranty of
 *  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 *  GNU General Public License for more details.
 *
 *  You should have received a copy of the GNU General Public License
 *  along with this program. If not, see <http://www.gnu.org/licenses/>.
 */

var direction = $("#asc").data('order');  // 0=Descending order; 1= ascending order
var sort = 0;       // Show sorted entries

// Detect if we're using hierarchy table (for authors) or classic list
var isHierarchyView = $(".hierarchy-table").length > 0;

// Get items to sort/filter based on view type
function getListItems() {
    if (isHierarchyView) {
        return $(".hierarchy-table tbody tr.author-row");
    } else {
        return $("#list").children(".row");
    }
}

// Get item name for sorting/filtering
function getItemName(element) {
    if (isHierarchyView) {
        return $(element).find("a").first().text().trim();
    } else {
        var store = element.attributes["data-id"];
        return store ? store.value : "";
    }
}

// Show/hide item
function showItem(element, show) {
    if (isHierarchyView) {
        var $row = $(element);
        var authorId = $row.data('id');
        var $detailsRow = $('#author-details-' + authorId);
        if (show) {
            $row.show();
        } else {
            $row.hide();
            $detailsRow.hide(); // Also hide details for hidden authors
        }
    } else {
        if (show) {
            $(element).show();
        } else {
            $(element).hide();
        }
    }
}

// Sort name toggle (B,A <-> A B)
$("#sort_name").click(function() {
    $("#sort_name").toggleClass("active");
    var className = $("h1").attr("Class") + "_sort_name";
    var obj = {};
    obj[className] = sort;

    if (isHierarchyView) {
        // For hierarchy view, swap between "Last, First" and "First Last" display
        $(".hierarchy-table tbody tr.author-row").each(function() {
            var $link = $(this).find("a").first();
            var name = $link.text().trim();
            var parts = name.split(", ");
            if (parts.length === 2 && sort === 0) {
                // "Last, First" -> "First Last"
                $link.text(parts[1] + " " + parts[0]);
            } else if (parts.length === 1 && name.includes(" ") && sort === 1) {
                // "First Last" -> "Last, First"
                var words = name.split(" ");
                var lastName = words.pop();
                $link.text(lastName + ", " + words.join(" "));
            }
        });
    } else {
        // Original list view logic
        var count = 0;
        var index = 0;
        var store;
        var cnt = $("#second").contents();
        $("#list").append(cnt);
        var listItems = $("#list").children(".row");
        var listlength = listItems.length;
        
        $(".row").each(function() {
            if (sort === 1) {
                store = this.attributes["data-name"];
            } else {
                store = this.attributes["data-id"];
            }
            $(this).find("a").html(store.value);
            if ($(this).css("display") !== "none") {
                count++;
            }
        });

        if (count > 20) {
            var middle = parseInt(count / 2, 10) + (count % 2);
            $(".row").each(function() {
                index++;
                if ($(this).css("display") !== "none") {
                    middle--;
                    if (middle <= 0) {
                        return false;
                    }
                }
            });
            $("#second").append(listItems.slice(index, listlength));
        }
    }
    sort = (sort + 1) % 2;
});

// Descending order
$("#desc").click(function() {
    if (direction === 0) {
        return;
    }
    $("#asc").removeClass("active");
    $("#desc").addClass("active");

    var page = $(this).data("id");
    $.ajax({
        method:"post",
        contentType: "application/json; charset=utf-8",
        dataType: "json",
        url: getPath() + "/ajax/view",
        data: "{\"" + page + "\": {\"dir\": \"desc\"}}",
    });

    if (isHierarchyView) {
        // Sort hierarchy table rows
        var $tbody = $(".hierarchy-table tbody");
        var rows = $tbody.find("tr.author-row").get();
        
        rows.sort(function(a, b) {
            var nameA = $(a).find("a").first().text().trim().toUpperCase();
            var nameB = $(b).find("a").first().text().trim().toUpperCase();
            return nameB.localeCompare(nameA); // Descending
        });
        
        // Reattach rows with their detail rows
        $.each(rows, function(idx, row) {
            var authorId = $(row).data('id');
            var $detailRow = $('#author-details-' + authorId);
            $tbody.append(row);
            if ($detailRow.length) {
                $tbody.append($detailRow);
            }
        });
    } else {
        // Original list view logic
        var index = 0;
        var list = $("#list");
        var second = $("#second");
        list.append(second.contents());
        var listItems = list.children(".row");
        var reversed, elementLength, middle;
        reversed = listItems.get().reverse();
        elementLength = reversed.length;
        var count = $(".row:visible").length;
        if (count > 20) {
            middle = parseInt(count / 2, 10) + (count % 2);
            $(reversed).each(function() {
                index++;
                if ($(this).css("display") !== "none") {
                    middle--;
                    if (middle <= 0) {
                        return false;
                    }
                }
            });
            list.append(reversed.slice(0, index));
            second.append(reversed.slice(index, elementLength));
        } else {
            list.append(reversed.slice(0, elementLength));
        }
    }
    direction = 0;
});

// Ascending order
$("#asc").click(function() {
    if (direction === 1) {
        return;
    }
    $("#desc").removeClass("active");
    $("#asc").addClass("active");

    var page = $(this).data("id");
    $.ajax({
        method:"post",
        contentType: "application/json; charset=utf-8",
        dataType: "json",
        url: getPath() + "/ajax/view",
        data: "{\"" + page + "\": {\"dir\": \"asc\"}}",
    });

    if (isHierarchyView) {
        // Sort hierarchy table rows
        var $tbody = $(".hierarchy-table tbody");
        var rows = $tbody.find("tr.author-row").get();
        
        rows.sort(function(a, b) {
            var nameA = $(a).find("a").first().text().trim().toUpperCase();
            var nameB = $(b).find("a").first().text().trim().toUpperCase();
            return nameA.localeCompare(nameB); // Ascending
        });
        
        // Reattach rows with their detail rows
        $.each(rows, function(idx, row) {
            var authorId = $(row).data('id');
            var $detailRow = $('#author-details-' + authorId);
            $tbody.append(row);
            if ($detailRow.length) {
                $tbody.append($detailRow);
            }
        });
    } else {
        // Original list view logic
        var index = 0;
        var list = $("#list");
        var second = $("#second");
        list.append(second.contents());
        var listItems = list.children(".row");
        var reversed = listItems.get().reverse();
        var elementLength = reversed.length;
        var count = $(".row:visible").length;
        if (count > 20) {
            var middle = parseInt(count / 2, 10) + (count % 2);
            $(reversed).each(function() {
                index++;
                if ($(this).css("display") !== "none") {
                    middle--;
                    if (middle <= 0) {
                        return false;
                    }
                }
            });
            list.append(reversed.slice(0, index));
            second.append(reversed.slice(index, elementLength));
        } else {
            list.append(reversed.slice(0, elementLength));
        }
    }
    direction = 1;
});

// Show all
$("#all").click(function() {
    $("#all").addClass("active");
    $(".char").removeClass("active");
    
    if (isHierarchyView) {
        // Show all authors in hierarchy view
        $(".hierarchy-table tbody tr.author-row").each(function() {
            $(this).show();
        });
    } else {
        // Original list view logic
        var cnt = $("#second").contents();
        $("#list").append(cnt);
        var listItems = $("#list").children(".row");
        var listlength = listItems.length;
        var middle = parseInt(listlength / 2, 10) + (listlength % 2);
        listItems.each(function() {
            $(this).show();
        });
        if (listlength > 20) {
            $("#second").append(listItems.slice(middle, listlength));
        }
    }
});

// Character filter
$(".char").click(function() {
    $(".char").removeClass("active");
    $(this).addClass("active");
    $("#all").removeClass("active");
    var character = this.innerText.toUpperCase();
    
    if (isHierarchyView) {
        // Filter hierarchy table by character
        $(".hierarchy-table tbody tr.author-row").each(function() {
            var name = $(this).find("a").first().text().trim();
            var firstChar = name.charAt(0).toUpperCase();
            var authorId = $(this).data('id');
            var $detailsRow = $('#author-details-' + authorId);
            
            if (firstChar === character) {
                $(this).show();
            } else {
                $(this).hide();
                $detailsRow.hide(); // Also hide expanded details
            }
        });
    } else {
        // Original list view logic
        var count = 0;
        var index = 0;
        var cnt = $("#second").contents();
        $("#list").append(cnt);
        var listItems = $("#list").children(".row");
        var listlength = listItems.length;
        
        $(".row").each(function() {
            if (this.attributes["data-id"].value.charAt(0).toUpperCase() !== character) {
                $(this).hide();
            } else {
                $(this).show();
                count++;
            }
        });
        if (count > 20) {
            var middle = parseInt(count / 2, 10) + (count % 2);
            $(".row").each(function() {
                index++;
                if ($(this).css("display") !== "none") {
                    middle--;
                    if (middle <= 0) {
                        return false;
                    }
                }
            });
            $("#second").append(listItems.slice(index, listlength));
        }
    }
});

